"""Mock adapter for the park's systems of record (catalog, camera feed, app).

Agents read from this class and never write to it: every mutation below is
called only by the engine's executor, after governance has ruled on the action.
Swapping in a Production Adapter means reimplementing these methods against the
real VinWonders catalogue and camera analytics, not touching any agent.

The numbers are the charter's: 6 phân khu, 220 điểm dịch vụ tại Nha Trang. Only
the ~20 service points the hero flow touches are named; the rest are generated
from a fixed seed so zone density is realistic and the same on every replay.

`inject_failure` exists so the retry/re-plan path can be exercised on demand.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import Field

from src.flow_crew.clock import at
from src.flow_crew.contracts import (
    FrozenContract,
    Itinerary,
    ItinerarySlot,
    StateModel,
    WaitSource,
)

SEED = 20260916
TOTAL_SERVICE_POINTS = 220

# Ngưỡng vận hành đã cấu hình sẵn. A2 đọc từ đây — mục 6: không tự đặt ngưỡng riêng.
ZONE_ALERT_LOAD_PCT = 85.0
ZONE_CROWDED_LOAD_PCT = 70.0
ZONE_OVERLOAD_LOAD_PCT = 100.0
# Hạn mức fast-pass trong ca; A3 không được tự nâng (mục 6).
FAST_PASS_SHIFT_CAP = 60
# Khách chỉ được điều hướng sang outlet trong bán kính đi bộ này.
WALKABLE_METERS = 450.0
WALK_SPEED_M_PER_MIN = 70.0
SLOT_MINUTES = 30
# Tải 100% nghĩa là khu đang phục vụ hết công suất thoải mái, chưa phải sập —
# camera đếm đầu người, công suất quy đổi về cùng đơn vị bằng hệ số này.
CAPACITY_COMFORT_DIVISOR = 1.85
# Khi một dịch vụ đóng: mỗi điểm lân cận chỉ hấp thụ thêm được chừng này công
# suất của nó, phần còn lại đi tiếp sang khu kế bên.
SPILL_INTAKE_RATIO = 0.2
SPILL_TREND_BUMP_PCT = 3.0
# Đám đông rời một sân khấu lớn tìm tới điểm có sức chứa tương đương, không xếp
# hàng ở quầy nhỏ — nên chỉ những điểm từ mức này trở lên mới hứng được dòng đó.
MIN_SPILL_RECEIVER_CAPACITY = 150
# Đầu giờ chiều mỗi khu đông một khác; đây là nền mô phỏng lấy theo camera.
ZONE_AFTERNOON_PRESSURE: dict[str, float] = {
    "Z-FEST": 0.80,
    "Z-FAIRY": 1.20,
    "Z-SEA": 1.05,
    "Z-GARDEN": 0.90,
    "Z-KING": 1.00,
    "Z-WATER": 1.00,
}


class ParkDataError(LookupError):
    """A record the caller named does not exist in the systems of record."""


class ToolUnavailableError(RuntimeError):
    """A park system did not answer; the engine decides what happens next."""


class ServiceKind(StrEnum):
    RIDE = "ride"
    SHOW = "show"
    WALKTHROUGH = "walkthrough"
    WATER = "water"
    FNB = "fnb"
    RETAIL = "retail"


class ServiceStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    PAUSED_SAFETY = "paused_safety"


class Zone(FrozenContract):
    zone_id: str
    name: str
    x_m: float
    y_m: float


ZONES: tuple[Zone, ...] = (
    Zone(zone_id="Z-FEST", name="Festive Hill", x_m=0, y_m=0),
    Zone(zone_id="Z-FAIRY", name="Fairy Land", x_m=380, y_m=120),
    Zone(zone_id="Z-SEA", name="Sea World", x_m=700, y_m=60),
    Zone(zone_id="Z-GARDEN", name="The World Garden", x_m=980, y_m=320),
    Zone(zone_id="Z-KING", name="King's Garden", x_m=520, y_m=520),
    Zone(zone_id="Z-WATER", name="Công viên nước Thiên đường Nhiệt đới", x_m=150, y_m=480),
)

ZONE_BY_ID: dict[str, Zone] = {zone.zone_id: zone for zone in ZONES}


class ServicePoint(StateModel):
    """Một điểm dịch vụ, kèm toạ độ thật — mục 1: khoảng cách là căn cứ, không đoán."""

    service_id: str
    name: str
    zone_id: str
    kind: ServiceKind
    x_m: float
    y_m: float
    opens_at: datetime
    closes_at: datetime
    status: ServiceStatus = ServiceStatus.OPEN
    min_height_cm: int = 0
    min_age: int = 0
    outdoor: bool = False
    slot_capacity: int = Field(default=0, ge=0)
    session_starts: tuple[datetime, ...] = ()
    supports_fast_pass: bool = False
    supports_reservation: bool = False
    booking_system: bool = False
    phone: str = ""
    throughput_per_hour: int = Field(default=1, ge=1)
    queue_count: int = Field(default=0, ge=0)
    wait_source: WaitSource = WaitSource.ESTIMATE
    extra_lane_open: bool = False
    booked: dict[str, int] = Field(default_factory=dict)

    @property
    def capacity_now(self) -> int:
        return self.throughput_per_hour * (2 if self.extra_lane_open else 1)

    def is_open_between(self, start: datetime, end: datetime) -> bool:
        return self.status == ServiceStatus.OPEN and self.opens_at <= start and end <= self.closes_at


class GuestParty(FrozenContract):
    """Ràng buộc khai thác từ khách — A1 lọc cứng theo đây trước khi gợi ý."""

    adults: int = Field(ge=1)
    children: int = Field(default=0, ge=0)
    shortest_height_cm: int = Field(default=170, ge=60)
    youngest_age: int = Field(default=18, ge=0)
    thrill_ok: bool = True

    @property
    def size(self) -> int:
        return self.adults + self.children


class Guest(FrozenContract):
    guest_id: str
    name: str
    language: str = "vi"
    party: GuestParty
    arrives_at: datetime
    leaves_at: datetime


class ReservationStatus(StrEnum):
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class ContactChannel(StrEnum):
    """Mục 6 · A4: hệ thống đặt bàn → tin nhắn → cuối cùng mới gọi điện."""

    BOOKING_SYSTEM = "booking_system"
    SMS = "sms"
    PHONE = "phone"


class Reservation(StateModel):
    reservation_id: str
    guest_id: str
    outlet_id: str
    outlet_name: str
    at: datetime
    party_size: int = Field(ge=1)
    status: ReservationStatus = ReservationStatus.CONFIRMED
    confirmation_code: str
    cancel_attempts: int = Field(default=0, ge=0)
    callbacks_used: int = Field(default=0, ge=0)
    evidence: list[str] = Field(default_factory=list)


class CallOutcome(FrozenContract):
    """Bằng chứng của một cuộc gọi tự động — mục 6 yêu cầu ghi lại đầy đủ."""

    outlet_id: str
    reached: bool
    duration_seconds: int = Field(ge=0)
    transcript: tuple[str, ...] = ()
    handed_to_human: bool = False


class Promotion(FrozenContract):
    promotion_id: str
    outlet_id: str
    audience: int = Field(gt=0)
    sent_at: datetime


class OutboundMessage(FrozenContract):
    at: datetime
    guest_id: str
    text: str


def distance_m(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
    return round(((a_x - b_x) ** 2 + (a_y - b_y) ** 2) ** 0.5, 1)


def walk_minutes(distance: float) -> int:
    return max(1, round(distance / WALK_SPEED_M_PER_MIN))


def _window_key(start: datetime) -> str:
    return start.isoformat(timespec="minutes")


def _named_services() -> list[ServicePoint]:
    """Các điểm dịch vụ hero flow chạm tới. Toạ độ và giờ mở lấy theo phân khu."""

    open_all_day = {"opens_at": at(9, 0), "closes_at": at(21, 30)}
    return [
        # --- Sea World: nơi sự cố 14:05 xảy ra ---
        ServicePoint(
            service_id="SW-DOLPHIN",
            name="Sân khấu Cá heo",
            zone_id="Z-SEA",
            kind=ServiceKind.SHOW,
            x_m=700,
            y_m=60,
            **open_all_day,
            slot_capacity=900,
            session_starts=(at(11, 0), at(14, 30), at(17, 30)),
            throughput_per_hour=900,
            queue_count=760,
            wait_source=WaitSource.CAMERA,
            supports_fast_pass=True,
        ),
        ServicePoint(
            service_id="SW-AQUA",
            name="Đường hầm Thuỷ cung",
            zone_id="Z-SEA",
            kind=ServiceKind.WALKTHROUGH,
            x_m=770,
            y_m=110,
            **open_all_day,
            slot_capacity=60,
            throughput_per_hour=480,
            queue_count=210,
            wait_source=WaitSource.CAMERA,
            supports_fast_pass=True,
        ),
        ServicePoint(
            service_id="SW-SEALION",
            name="Sân khấu Hải cẩu",
            zone_id="Z-SEA",
            kind=ServiceKind.SHOW,
            x_m=640,
            y_m=140,
            **open_all_day,
            slot_capacity=40,
            session_starts=(at(11, 0), at(15, 0), at(17, 30)),
            throughput_per_hour=240,
            queue_count=150,
            wait_source=WaitSource.CAMERA,
            supports_fast_pass=True,
        ),
        ServicePoint(
            service_id="SW-SPLASH",
            name="Tàu lượn Sóng thần",
            zone_id="Z-SEA",
            kind=ServiceKind.RIDE,
            x_m=820,
            y_m=40,
            **open_all_day,
            status=ServiceStatus.PAUSED_SAFETY,
            min_height_cm=120,
            min_age=8,
            outdoor=True,
            slot_capacity=48,
            throughput_per_hour=320,
            queue_count=0,
            wait_source=WaitSource.CAMERA,
        ),
        ServicePoint(
            service_id="FB-OCEAN",
            name="Nhà hàng Ocean Deck",
            zone_id="Z-SEA",
            kind=ServiceKind.FNB,
            x_m=735,
            y_m=150,
            **open_all_day,
            throughput_per_hour=180,
            queue_count=95,
            wait_source=WaitSource.CAMERA,
            supports_reservation=True,
            booking_system=True,
            phone="+84258380001",
        ),
        ServicePoint(
            service_id="FB-LAGOON",
            name="Quán Lagoon BBQ",
            zone_id="Z-SEA",
            kind=ServiceKind.FNB,
            x_m=880,
            y_m=200,
            **open_all_day,
            throughput_per_hour=120,
            queue_count=18,
            wait_source=WaitSource.CAMERA,
            supports_reservation=True,
            booking_system=False,
            phone="+84258380002",
        ),
        # --- Fairy Land: khu liền kề, hứng phần khách dồn sang ---
        ServicePoint(
            service_id="FL-CASTLE",
            name="Lâu đài Cổ tích",
            zone_id="Z-FAIRY",
            kind=ServiceKind.WALKTHROUGH,
            x_m=380,
            y_m=120,
            **open_all_day,
            slot_capacity=50,
            throughput_per_hour=300,
            queue_count=240,
            wait_source=WaitSource.CAMERA,
        ),
        ServicePoint(
            service_id="FL-CAROUSEL",
            name="Vòng quay Ngựa gỗ",
            zone_id="Z-FAIRY",
            kind=ServiceKind.RIDE,
            x_m=420,
            y_m=175,
            **open_all_day,
            min_height_cm=100,
            slot_capacity=36,
            throughput_per_hour=200,
            queue_count=165,
            wait_source=WaitSource.ESTIMATE,
        ),
        ServicePoint(
            service_id="FB-FAIRY-DELI",
            name="Fairy Deli",
            zone_id="Z-FAIRY",
            kind=ServiceKind.FNB,
            x_m=350,
            y_m=95,
            **open_all_day,
            throughput_per_hour=150,
            queue_count=132,
            wait_source=WaitSource.CAMERA,
            supports_reservation=True,
            booking_system=True,
            phone="+84258380003",
        ),
        # --- Festive Hill ---
        ServicePoint(
            service_id="FH-TATA",
            name="Tata Show · Quảng trường Thần Thoại",
            zone_id="Z-FEST",
            kind=ServiceKind.SHOW,
            opens_at=at(19, 30),
            closes_at=at(21, 30),
            x_m=0,
            y_m=0,
            slot_capacity=2400,
            session_starts=(at(19, 45),),
            throughput_per_hour=2400,
            queue_count=0,
            wait_source=WaitSource.CAMERA,
            outdoor=True,
        ),
        ServicePoint(
            service_id="FH-SKY",
            name="Đu quay Sky Wheel",
            zone_id="Z-FEST",
            kind=ServiceKind.RIDE,
            x_m=60,
            y_m=70,
            **open_all_day,
            min_height_cm=110,
            outdoor=True,
            slot_capacity=40,
            throughput_per_hour=260,
            queue_count=88,
            wait_source=WaitSource.CAMERA,
            supports_fast_pass=True,
        ),
        ServicePoint(
            service_id="FB-HILL-CAFE",
            name="Hill Café",
            zone_id="Z-FEST",
            kind=ServiceKind.FNB,
            x_m=40,
            y_m=-30,
            **open_all_day,
            throughput_per_hour=140,
            queue_count=22,
            wait_source=WaitSource.CAMERA,
            supports_reservation=True,
            booking_system=True,
            phone="+84258380004",
        ),
        # --- The World Garden ---
        ServicePoint(
            service_id="TG-EXPRESS",
            name="Tàu hoả Vườn Thế Giới",
            zone_id="Z-GARDEN",
            kind=ServiceKind.RIDE,
            x_m=980,
            y_m=320,
            **open_all_day,
            outdoor=True,
            slot_capacity=44,
            throughput_per_hour=220,
            queue_count=54,
            wait_source=WaitSource.ESTIMATE,
        ),
        ServicePoint(
            service_id="TG-GREENHOUSE",
            name="Nhà kính Bốn Mùa",
            zone_id="Z-GARDEN",
            kind=ServiceKind.WALKTHROUGH,
            x_m=1040,
            y_m=360,
            **open_all_day,
            slot_capacity=70,
            throughput_per_hour=340,
            queue_count=61,
            wait_source=WaitSource.CAMERA,
        ),
        # --- King's Garden ---
        ServicePoint(
            service_id="KG-SAFARI",
            name="Xe điện Safari Vườn Vua",
            zone_id="Z-KING",
            kind=ServiceKind.RIDE,
            x_m=520,
            y_m=520,
            **open_all_day,
            outdoor=True,
            slot_capacity=52,
            throughput_per_hour=260,
            queue_count=96,
            wait_source=WaitSource.CAMERA,
        ),
        ServicePoint(
            service_id="FB-KING-BBQ",
            name="King's BBQ Garden",
            zone_id="Z-KING",
            kind=ServiceKind.FNB,
            x_m=560,
            y_m=560,
            **open_all_day,
            throughput_per_hour=160,
            queue_count=24,
            wait_source=WaitSource.CAMERA,
            supports_reservation=True,
            booking_system=True,
            phone="+84258380005",
        ),
        # --- Công viên nước ---
        ServicePoint(
            service_id="WP-WAVE",
            name="Hồ tạo sóng Thiên đường",
            zone_id="Z-WATER",
            kind=ServiceKind.WATER,
            x_m=150,
            y_m=480,
            **open_all_day,
            outdoor=True,
            min_height_cm=100,
            slot_capacity=300,
            throughput_per_hour=600,
            queue_count=180,
            wait_source=WaitSource.CAMERA,
        ),
        ServicePoint(
            service_id="WP-SLIDE",
            name="Máng trượt Xoắn ốc",
            zone_id="Z-WATER",
            kind=ServiceKind.WATER,
            x_m=190,
            y_m=520,
            **open_all_day,
            outdoor=True,
            min_height_cm=130,
            min_age=10,
            slot_capacity=40,
            throughput_per_hour=200,
            queue_count=140,
            wait_source=WaitSource.ESTIMATE,
            supports_fast_pass=True,
        ),
    ]


def _filler_services(rng: random.Random, start_index: int) -> list[ServicePoint]:
    """Phần còn lại của 220 điểm dịch vụ: quầy ăn, cửa hàng, trò nhỏ trong từng khu."""

    kinds = (ServiceKind.RETAIL, ServiceKind.FNB, ServiceKind.RIDE)
    services: list[ServicePoint] = []
    for index in range(start_index, TOTAL_SERVICE_POINTS + 1):
        zone = ZONES[index % len(ZONES)]
        kind = kinds[index % len(kinds)]
        throughput = rng.choice((60, 80, 110, 140))
        # Toả thành vành đai quanh lõi khu, để các điểm chính vẫn là nơi gần nhất
        # khi khách phải rời một dịch vụ đóng cửa.
        bearing = rng.uniform(0, 6.283)
        radius = rng.uniform(80, 150)
        services.append(
            ServicePoint(
                service_id=f"SP-{index:03d}",
                name=f"{zone.name} · điểm dịch vụ {index:03d}",
                zone_id=zone.zone_id,
                kind=kind,
                x_m=zone.x_m + radius * math.cos(bearing),
                y_m=zone.y_m + radius * math.sin(bearing),
                opens_at=at(9, 0),
                closes_at=at(21, 30),
                outdoor=kind is ServiceKind.RIDE,
                min_height_cm=100 if kind is ServiceKind.RIDE else 0,
                slot_capacity=20 if kind is ServiceKind.RIDE else 0,
                throughput_per_hour=throughput,
                queue_count=int(throughput * rng.uniform(0.18, 0.44) * ZONE_AFTERNOON_PRESSURE[zone.zone_id]),
                wait_source=WaitSource.CAMERA if index % 3 == 0 else WaitSource.ESTIMATE,
            )
        )
    return services


_VN_NAMES = (
    "Minh", "Lan", "Hùng", "Trang", "Khoa", "Ngọc", "Bảo", "Thảo", "Duy", "Hà",
    "Phúc", "Mai", "Sơn", "Linh", "Tuấn", "Vy", "Đạt", "Chi", "Quân", "Nhi",
)


class MockPark:
    """Catalogue + camera feed + app state, all in memory."""

    def __init__(self) -> None:
        rng = random.Random(SEED)
        named = _named_services()
        services = named + _filler_services(rng, len(named) + 1)
        self.services: dict[str, ServicePoint] = {service.service_id: service for service in services}
        self.guests: dict[str, Guest] = {}
        self.itineraries: dict[str, Itinerary] = {}
        self.reservations: dict[str, Reservation] = {}
        self.promotions: list[Promotion] = []
        self.outbox: list[OutboundMessage] = []
        self.calls: list[CallOutcome] = []
        self.fast_passes_issued: int = 0
        # Xu hướng tải từng khu (%/10 phút) do phân tích camera cung cấp.
        self.zone_trend_pct: dict[str, float] = {
            "Z-FEST": 0.4,
            "Z-FAIRY": 1.1,
            "Z-SEA": 1.3,
            "Z-GARDEN": 0.2,
            "Z-KING": 0.5,
            "Z-WATER": 0.8,
        }
        # Dự báo mưa theo giờ — A1 không xếp hoạt động ngoài trời vào khung có mưa.
        self.rain_hours: frozenset[int] = frozenset({16, 17})
        # Số khách dùng app đang ở trong từng khu (dữ liệu tổng hợp, không danh tính).
        self.app_users_in_zone: dict[str, int] = {
            "Z-FEST": 120,
            "Z-FAIRY": 165,
            "Z-SEA": 200,
            "Z-GARDEN": 70,
            "Z-KING": 95,
            "Z-WATER": 140,
        }
        # Khách đang ở trong khu nhưng không xếp hàng ở đâu cả.
        self.wandering: dict[str, int] = {zone.zone_id: 0 for zone in ZONES}
        self._failures: dict[str, int] = {}
        self._seed_guests(rng)

    # ---- seed ---------------------------------------------------------------

    def _seed_guests(self, rng: random.Random) -> None:
        """60 khách đang dùng app; 40 người có suất Cá heo 14:30 trong lịch."""

        show_start = at(14, 30)
        for index in range(1, 61):
            guest_id = f"G-{index:03d}"
            with_children = index % 4 == 0
            party = GuestParty(
                adults=2,
                children=2 if with_children else 0,
                shortest_height_cm=105 if with_children else 168,
                youngest_age=6 if with_children else 28,
                thrill_ok=not with_children,
            )
            self.guests[guest_id] = Guest(
                guest_id=guest_id,
                name=f"Khách {_VN_NAMES[index % len(_VN_NAMES)]} ({guest_id})",
                party=party,
                arrives_at=at(9, 30),
                leaves_at=at(17, 0) if index % 5 == 0 else at(20, 30),
            )
            slots = [
                ItinerarySlot(
                    service_id="FL-CASTLE",
                    service_name=self.services["FL-CASTLE"].name,
                    zone_id="Z-FAIRY",
                    start=at(13, 0),
                    end=at(13, 40),
                )
            ]
            if index <= 40:
                slots.append(
                    ItinerarySlot(
                        service_id="SW-DOLPHIN",
                        service_name=self.services["SW-DOLPHIN"].name,
                        zone_id="Z-SEA",
                        start=show_start,
                        end=show_start + timedelta(minutes=45),
                    )
                )
            else:
                slots.append(
                    ItinerarySlot(
                        service_id="TG-GREENHOUSE",
                        service_name=self.services["TG-GREENHOUSE"].name,
                        zone_id="Z-GARDEN",
                        start=at(15, 0),
                        end=at(15, 40),
                    )
                )
            self.itineraries[guest_id] = Itinerary(guest_id=guest_id, slots=slots)

        # Ba khách trong nhóm 40 có lịch đặt bàn ngay sau suất diễn.
        for guest_id, outlet_id, moment, code in (
            ("G-014", "FB-OCEAN", at(15, 30), "OCD-4417"),
            ("G-021", "FB-OCEAN", at(15, 30), "OCD-4418"),
            ("G-025", "FB-LAGOON", at(15, 30), "LAG-2290"),
        ):
            outlet = self.services[outlet_id]
            reservation_id = f"RS-{guest_id[2:]}"
            self.reservations[reservation_id] = Reservation(
                reservation_id=reservation_id,
                guest_id=guest_id,
                outlet_id=outlet_id,
                outlet_name=outlet.name,
                at=moment,
                party_size=self.guests[guest_id].party.size,
                confirmation_code=code,
            )
            self.itineraries[guest_id].slots.append(
                ItinerarySlot(
                    service_id=outlet_id,
                    service_name=outlet.name,
                    zone_id=outlet.zone_id,
                    start=moment,
                    end=moment + timedelta(minutes=60),
                    locked=True,
                    note=f"Đã đặt bàn · {code}",
                )
            )

        # Khung 14:30 của hai dịch vụ thay thế đã kín từ sáng; chỗ trống sớm
        # nhất là khung 15:00 — 18 suất ở Thuỷ cung và 10 suất ở Hải cẩu. Đúng
        # 28 suất cho 40 lượt khách, nên 12 lượt sẽ không có phương án tốt.
        self.services["SW-AQUA"].booked[_window_key(show_start)] = 60
        self.services["SW-AQUA"].booked[_window_key(at(15, 0))] = 42
        self.services["SW-AQUA"].booked[_window_key(at(16, 0))] = 20
        self.services["SW-SEALION"].booked[_window_key(at(15, 0))] = 30
        # Chiều cao điểm: các điểm cùng tầm trong bán kính đi bộ đã kín suất từ
        # sáng. Đó là lý do 12 lượt còn lại không có phương án tốt — hết chỗ
        # thật, không phải vì agent lười tìm.
        for busy_id in ("FL-CASTLE", "FL-CAROUSEL", "TG-EXPRESS"):
            busy = self.services[busy_id]
            for hour, minute in ((14, 30), (15, 0), (15, 30), (16, 0), (16, 30)):
                busy.booked[_window_key(at(hour, minute))] = busy.slot_capacity

    # ---- đọc: catalogue ------------------------------------------------------

    def service(self, service_id: str) -> ServicePoint:
        try:
            return self.services[service_id]
        except KeyError as exc:
            raise ParkDataError(f"Không có điểm dịch vụ {service_id}") from exc

    def zone(self, zone_id: str) -> Zone:
        try:
            return ZONE_BY_ID[zone_id]
        except KeyError as exc:
            raise ParkDataError(f"Không có phân khu {zone_id}") from exc

    def services_in(self, zone_id: str) -> tuple[ServicePoint, ...]:
        return tuple(service for service in self.services.values() if service.zone_id == zone_id)

    def guest(self, guest_id: str) -> Guest:
        try:
            return self.guests[guest_id]
        except KeyError as exc:
            raise ParkDataError(f"Không có khách {guest_id}") from exc

    def itinerary(self, guest_id: str) -> Itinerary:
        try:
            return self.itineraries[guest_id]
        except KeyError as exc:
            raise ParkDataError(f"Khách {guest_id} chưa có lịch trình") from exc

    def reservation(self, reservation_id: str) -> Reservation:
        try:
            return self.reservations[reservation_id]
        except KeyError as exc:
            raise ParkDataError(f"Không có lịch đặt {reservation_id}") from exc

    def reservations_of(self, guest_id: str) -> tuple[Reservation, ...]:
        return tuple(item for item in self.reservations.values() if item.guest_id == guest_id)

    # ---- đọc: mật độ (dữ liệu tổng hợp, A2 chỉ được thấy mức này) --------------

    def zone_headcount(self, zone_id: str) -> int:
        return sum(service.queue_count for service in self.services_in(zone_id)) + self.wandering[zone_id]

    def zone_capacity(self, zone_id: str) -> int:
        """Năng lực phục vụ của khu — chỉ tính dịch vụ đang mở.

        Đóng một dịch vụ lớn không làm khách biến mất, nó rút năng lực ra khỏi
        khu; đó là lý do tải bật lên ngay khi Sân khấu Cá heo ngừng hoạt động.
        """

        open_capacity = sum(
            service.capacity_now
            for service in self.services_in(zone_id)
            if service.status == ServiceStatus.OPEN
        )
        return max(1, round(open_capacity / CAPACITY_COMFORT_DIVISOR))

    def zone_load_pct(self, zone_id: str) -> float:
        return round(self.zone_headcount(zone_id) / self.zone_capacity(zone_id) * 100, 1)

    def hottest_service(self, zone_id: str) -> ServicePoint | None:
        candidates = [s for s in self.services_in(zone_id) if s.status == ServiceStatus.OPEN]
        if not candidates:
            return None
        return max(candidates, key=lambda service: service.queue_count / max(1, service.capacity_now))

    def wait_minutes(self, service_id: str) -> int:
        service = self.service(service_id)
        if service.status != ServiceStatus.OPEN:
            return 0
        return round(service.queue_count / max(1, service.capacity_now) * 60)

    def guests_heading_to(self, service_id: str, *, after: datetime) -> int:
        """Số đếm tổng hợp, không kèm danh tính — mục 6 · A2 không đọc lịch riêng."""

        return sum(
            1
            for itinerary in self.itineraries.values()
            for slot in itinerary.slots
            if slot.service_id == service_id and slot.start >= after
        )

    def guest_ids_heading_to(self, service_id: str, *, after: datetime) -> tuple[str, ...]:
        """Danh sách khách — chỉ A1 (chủ quản lịch trình) được gọi."""

        return tuple(
            sorted(
                itinerary.guest_id
                for itinerary in self.itineraries.values()
                for slot in itinerary.slots
                if slot.service_id == service_id and slot.start >= after
            )
        )

    # ---- đọc: chỗ trống ------------------------------------------------------

    def rains_at(self, moment: datetime) -> bool:
        return moment.hour in self.rain_hours

    def free_capacity(self, service_id: str, window_start: datetime) -> int:
        service = self.service(service_id)
        if service.slot_capacity <= 0:
            return 0
        if service.session_starts and window_start not in service.session_starts:
            return 0
        return max(0, service.slot_capacity - service.booked.get(_window_key(window_start), 0))

    def next_window_with_room(
        self, service_id: str, *, after: datetime, before: datetime, party_size: int
    ) -> datetime | None:
        """Khung kế tiếp còn chỗ — căn cứ để A4 thử đổi thứ tự lộ trình trước."""

        service = self.service(service_id)
        candidates: tuple[datetime, ...]
        if service.session_starts:
            candidates = service.session_starts
        else:
            candidates = tuple(
                service.opens_at + timedelta(minutes=SLOT_MINUTES * step)
                for step in range(int((service.closes_at - service.opens_at).total_seconds() // 60 // SLOT_MINUTES))
            )
        for window in candidates:
            if window <= after or window >= before:
                continue
            if self.free_capacity(service_id, window) >= party_size:
                return window
        return None

    def nearby_quiet_outlets(
        self, service_id: str, *, limit: int = 3, avoid_zone_ids: frozenset[str] = frozenset()
    ) -> tuple[ServicePoint, ...]:
        """Outlet F&B đang vắng, trong tầm đi bộ — căn cứ điều hướng của A3.

        `avoid_zone_ids` để không bao giờ đẩy khách từ khu nghẽn này sang một
        khu cũng đang nghẽn: đó là dời điểm nóng, không phải giải nó.
        """

        origin = self.service(service_id)
        found: list[tuple[float, ServicePoint]] = []
        for candidate in self.services.values():
            if candidate.kind is not ServiceKind.FNB or candidate.status != ServiceStatus.OPEN:
                continue
            if candidate.zone_id != origin.zone_id and candidate.zone_id in avoid_zone_ids:
                continue
            load = candidate.queue_count / max(1, candidate.capacity_now)
            if load >= 0.5:
                continue
            gap = distance_m(origin.x_m, origin.y_m, candidate.x_m, candidate.y_m)
            if gap > WALKABLE_METERS:
                continue
            found.append((gap, candidate))
        found.sort(key=lambda pair: pair[0])
        return tuple(service for _, service in found[:limit])

    def eligible_for(self, service: ServicePoint, party: GuestParty) -> bool:
        if party.shortest_height_cm < service.min_height_cm:
            return False
        if party.youngest_age < service.min_age:
            return False
        # Trò cảm giác mạnh ngoài trời chỉ gợi ý cho nhóm đã nói là thích.
        return party.thrill_ok or not (service.kind is ServiceKind.RIDE and service.outdoor)

    # ---- ghi: chỉ engine gọi, sau khi governance đã phán ----------------------

    def inject_failure(self, tool: str, times: int = 1) -> None:
        self._failures[tool] = times

    def _maybe_fail(self, tool: str) -> None:
        remaining = self._failures.get(tool, 0)
        if remaining > 0:
            self._failures[tool] = remaining - 1
            raise ToolUnavailableError(f"Hệ thống {tool} không phản hồi")

    def close_service(self, service_id: str, now: datetime, *, spill_ratio: float = 0.85) -> tuple[str, ...]:
        """Đóng một dịch vụ; hàng chờ của nó dồn sang các điểm mở gần nhất.

        Đây là cơ chế sinh ra điểm nghẽn trong hero flow: tải tăng vì khách phải
        đi đâu đó, không phải vì một con số được gán sẵn.
        """

        self._maybe_fail("catalog")
        service = self.service(service_id)
        service.status = ServiceStatus.CLOSED
        spill = int(service.queue_count * spill_ratio)
        service.queue_count = 0
        receivers = sorted(
            (
                candidate
                for candidate in self.services.values()
                if candidate.status == ServiceStatus.OPEN
                and candidate.kind in {ServiceKind.SHOW, ServiceKind.WALKTHROUGH, ServiceKind.RIDE}
                and candidate.capacity_now >= MIN_SPILL_RECEIVER_CAPACITY
                and candidate.opens_at <= now <= candidate.closes_at
                and distance_m(service.x_m, service.y_m, candidate.x_m, candidate.y_m) <= WALKABLE_METERS
            ),
            key=lambda candidate: distance_m(service.x_m, service.y_m, candidate.x_m, candidate.y_m),
        )
        # Khách đi tới chỗ gần nhất trước; khi chỗ đó đã kín thì mới đi xa hơn,
        # nên phần tràn tự nhiên lan sang khu kế bên thay vì chia đều cho đẹp.
        touched: list[str] = []
        for receiver in receivers:
            if spill <= 0:
                break
            headroom = max(0, receiver.capacity_now - receiver.queue_count)
            # Không điểm nào nuốt trọn một sân khấu: mỗi nơi chỉ hấp thụ thêm
            # được một phần công suất của mình trước khi khách đi tiếp.
            taken = min(spill, headroom, max(1, round(receiver.capacity_now * SPILL_INTAKE_RATIO)))
            if taken <= 0:
                continue
            receiver.queue_count += taken
            spill -= taken
            touched.append(receiver.service_id)
        # Ai không đi đâu được thì đứng lại trong khu — đó mới là phần làm tải
        # của Sea World bật lên, không phải họ biến mất khỏi công viên.
        if spill > 0:
            self.wandering[service.zone_id] += spill
        for zone_id in {self.service(receiver_id).zone_id for receiver_id in touched} | {service.zone_id}:
            self.zone_trend_pct[zone_id] = round(self.zone_trend_pct[zone_id] + SPILL_TREND_BUMP_PCT, 2)
        return tuple(touched)

    def book_slot(self, service_id: str, window_start: datetime, seats: int) -> None:
        self._maybe_fail("catalog")
        if self.free_capacity(service_id, window_start) < seats:
            raise ParkDataError(f"{service_id} không còn {seats} chỗ lúc {window_start:%H:%M}")
        key = _window_key(window_start)
        service = self.service(service_id)
        service.booked[key] = service.booked.get(key, 0) + seats

    def release_slot(self, service_id: str, window_start: datetime, seats: int) -> None:
        key = _window_key(window_start)
        service = self.service(service_id)
        service.booked[key] = max(0, service.booked.get(key, 0) - seats)

    def apply_itinerary(self, itinerary: Itinerary) -> None:
        self._maybe_fail("app")
        itinerary.version += 1
        self.itineraries[itinerary.guest_id] = itinerary

    def open_extra_lane(self, service_id: str) -> None:
        self._maybe_fail("ops")
        service = self.service(service_id)
        if service.status == ServiceStatus.PAUSED_SAFETY:
            raise ParkDataError(f"{service.name} đang tạm dừng vì an toàn, không mở làn phụ")
        service.extra_lane_open = True

    def push_promotion(self, *, promotion_id: str, outlet_id: str, audience: int, at_time: datetime) -> Promotion:
        self._maybe_fail("marketing")
        promotion = Promotion(promotion_id=promotion_id, outlet_id=outlet_id, audience=audience, sent_at=at_time)
        self.promotions.append(promotion)
        return promotion

    def grant_fast_pass(self, guest_ids: tuple[str, ...], service_id: str) -> int:
        self._maybe_fail("ticketing")
        if self.fast_passes_issued + len(guest_ids) > FAST_PASS_SHIFT_CAP:
            raise ParkDataError("Vượt hạn mức fast-pass của ca")
        service = self.service(service_id)
        if not service.supports_fast_pass:
            raise ParkDataError(f"{service.name} không hỗ trợ fast-pass")
        self.fast_passes_issued += len(guest_ids)
        return self.fast_passes_issued

    def reroute_guests(self, *, from_service_id: str, to_service_id: str, headcount: int) -> None:
        self._maybe_fail("ops")
        source = self.service(from_service_id)
        target = self.service(to_service_id)
        moved = min(headcount, source.queue_count)
        source.queue_count -= moved
        target.queue_count += moved

    def send_guest_message(self, guest_id: str, text: str, *, at_time: datetime) -> OutboundMessage:
        self._maybe_fail("app")
        message = OutboundMessage(at=at_time, guest_id=guest_id, text=text)
        self.outbox.append(message)
        return message

    def move_reservation(self, reservation_id: str, new_time: datetime) -> Reservation:
        self._maybe_fail("booking")
        reservation = self.reservation(reservation_id)
        reservation.at = new_time
        reservation.status = ReservationStatus.RESCHEDULED
        return reservation

    def cancel_reservation(self, reservation_id: str) -> Reservation:
        self._maybe_fail("booking")
        reservation = self.reservation(reservation_id)
        if reservation.status == ReservationStatus.CANCELLED:
            raise ParkDataError(f"Lịch đặt {reservation_id} đã huỷ trước đó")
        reservation.cancel_attempts += 1
        reservation.status = ReservationStatus.CANCELLED
        return reservation

    def call_partner(self, outlet_id: str, transcript: tuple[str, ...], *, seconds: int, reached: bool) -> CallOutcome:
        self._maybe_fail("telephony")
        outcome = CallOutcome(
            outlet_id=outlet_id,
            reached=reached,
            duration_seconds=seconds,
            transcript=transcript,
            handed_to_human=not reached,
        )
        self.calls.append(outcome)
        return outcome
