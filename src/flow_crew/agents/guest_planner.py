"""A1 · Guest Planner — phục vụ khách hàng.

Hướng dẫn viên cá nhân hoá, không phải một bản lịch trình chung in sẵn. Hai
điều ở mục 6 được cài vào chính chữ ký hàm chứ không để cho prompt nhớ hộ:

* lọc cứng trước khi gợi ý — chiều cao, độ tuổi, giờ hoạt động, mưa cho hoạt
  động ngoài trời, dịch vụ đang tạm dừng vì an toàn;
* chỉ sửa đúng phần cần sửa, và không bao giờ dời mốc khách đã chốt — hàm trả
  về `ItineraryPatch` (phần thay đổi), không bao giờ trả về một lịch mới.

Agent trả về kế hoạch; ghi vào lịch trình là việc của engine sau khi
governance đã phán — nên 40 lượt khách được xếp tuần tự, không ai phát trùng
chỗ của ai.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.flow_crew.contracts import (
    ChangeKind,
    CrowdAlert,
    Itinerary,
    ItineraryChange,
    ItineraryPatch,
    ItinerarySlot,
    WaitEstimate,
)
from src.flow_crew.mock_park import (
    SLOT_MINUTES,
    WALKABLE_METERS,
    GuestParty,
    MockPark,
    ServiceKind,
    ServicePoint,
    ServiceStatus,
    distance_m,
)

# Thời lượng mặc định của một suất, theo loại dịch vụ.
DURATION_MINUTES: dict[ServiceKind, int] = {
    ServiceKind.SHOW: 45,
    ServiceKind.WALKTHROUGH: 40,
    ServiceKind.RIDE: 30,
    ServiceKind.WATER: 60,
    ServiceKind.FNB: 60,
    ServiceKind.RETAIL: 20,
}
PLANNABLE_KINDS = frozenset({ServiceKind.SHOW, ServiceKind.WALKTHROUGH, ServiceKind.RIDE, ServiceKind.WATER})
# Thay một suất diễn lớn bằng một trò nhỏ là gợi ý cho có: phương án thay thế
# phải cùng tầm sức chứa thì mới thực sự thay được.
MIN_REPLACEMENT_CAPACITY = 150
# Và phải cùng khung giờ trong ngày — đẩy khách sang buổi tối không phải là cứu
# lịch, đó là bỏ mục đó đi mà không nói.
REPLAN_WINDOW_MINUTES = 60


def duration_of(service: ServicePoint) -> timedelta:
    return timedelta(minutes=DURATION_MINUTES.get(service.kind, SLOT_MINUTES))


def is_allowed(park: MockPark, service: ServicePoint, party: GuestParty, start: datetime) -> bool:
    """Lọc cứng. Một dịch vụ không qua được hàm này thì không bao giờ được gợi ý."""

    if service.status != ServiceStatus.OPEN:
        return False
    if not service.is_open_between(start, start + duration_of(service)):
        return False
    if service.outdoor and park.rains_at(start):
        return False
    return park.eligible_for(service, party)


def alternatives(
    park: MockPark,
    *,
    origin_service_id: str,
    party: GuestParty,
    earliest: datetime,
    latest: datetime,
) -> tuple[tuple[ServicePoint, datetime], ...]:
    """Các phương án thay thế còn chỗ, gần nhất trước.

    Gần là khoảng cách thật giữa hai điểm dịch vụ — mục 1 nêu đúng khoảng trống
    này: hệ thống cũ biết chỗ nào đang đông, nhưng không biết chỗ nào gần đó có
    thể thay được.
    """

    origin = park.service(origin_service_id)
    found: list[tuple[float, ServicePoint, datetime]] = []
    for candidate in park.services.values():
        if candidate.service_id == origin_service_id or candidate.kind not in PLANNABLE_KINDS:
            continue
        if candidate.capacity_now < MIN_REPLACEMENT_CAPACITY:
            continue
        gap = distance_m(origin.x_m, origin.y_m, candidate.x_m, candidate.y_m)
        if gap > WALKABLE_METERS:
            continue
        window = park.next_window_with_room(
            candidate.service_id, after=earliest - timedelta(minutes=1), before=latest, party_size=1
        )
        if window is None or not is_allowed(park, candidate, party, window):
            continue
        found.append((gap, candidate, window))
    found.sort(key=lambda item: (item[0], item[2]))
    return tuple((service, window) for _, service, window in found)


def build_itinerary(park: MockPark, guest_id: str, *, now: datetime, max_items: int = 5) -> Itinerary:
    """US-1: khách hỏi thẳng "cho tôi lịch trình 1 ngày" — A1 dựng được ngay."""

    guest = park.guest(guest_id)
    cursor = max(now, guest.arrives_at)
    slots: list[ItinerarySlot] = []
    used: set[str] = set()
    while len(slots) < max_items and cursor < guest.leaves_at:
        options = [
            service
            for service in park.services.values()
            if service.service_id not in used
            and service.kind in PLANNABLE_KINDS
            and is_allowed(park, service, guest.party, cursor)
            and cursor + duration_of(service) <= guest.leaves_at
        ]
        if not options:
            cursor += timedelta(minutes=SLOT_MINUTES)
            continue
        # Chờ ngắn trước; đông bằng nhau thì lấy chỗ gần chỗ vừa chơi.
        anchor = park.service(slots[-1].service_id) if slots else park.service(options[0].service_id)
        options.sort(
            key=lambda service: (
                park.wait_minutes(service.service_id),
                distance_m(anchor.x_m, anchor.y_m, service.x_m, service.y_m),
            )
        )
        chosen = options[0]
        end = cursor + duration_of(chosen)
        slots.append(
            ItinerarySlot(
                service_id=chosen.service_id,
                service_name=chosen.name,
                zone_id=chosen.zone_id,
                start=cursor,
                end=end,
            )
        )
        used.add(chosen.service_id)
        cursor = end + timedelta(minutes=10)
    return Itinerary(guest_id=guest_id, slots=slots)


def replan(park: MockPark, guest_id: str, *, alert: CrowdAlert, now: datetime) -> ItineraryPatch:
    """Sửa đúng phần hỏng trong lịch của một khách, không dựng lại từ đầu."""

    if alert.service_id is None:
        return ItineraryPatch(guest_id=guest_id)
    itinerary = park.itinerary(guest_id)
    slot = itinerary.slot_for(alert.service_id)
    if slot is None or slot.start < now:
        return ItineraryPatch(guest_id=guest_id)
    if slot.locked:
        return ItineraryPatch(
            guest_id=guest_id,
            resolved=False,
            unresolved_reason="Khách đã chốt chắc chắn mốc này; không tự dời.",
        )

    guest = park.guest(guest_id)
    options = alternatives(
        park,
        origin_service_id=alert.service_id,
        party=guest.party,
        earliest=now,
        latest=min(guest.leaves_at, slot.start + timedelta(minutes=REPLAN_WINDOW_MINUTES)),
    )
    if not options:
        return ItineraryPatch(
            guest_id=guest_id,
            resolved=False,
            unresolved_reason="Không còn suất phù hợp ở các dịch vụ thay thế trong khung giờ của khách.",
        )
    service, window = options[0]
    return ItineraryPatch(
        guest_id=guest_id,
        changes=(
            ItineraryChange(
                kind=ChangeKind.REPLACED,
                from_service_id=slot.service_id,
                from_service_name=slot.service_name,
                to_service_id=service.service_id,
                to_service_name=service.name,
                new_start=window,
                reason=f"{slot.service_name} đóng đột xuất; chỗ gần nhất còn suất là {service.name}.",
            ),
        ),
    )


def reorder_around(
    park: MockPark, guest_id: str, *, protect_start: datetime, protect_end: datetime, now: datetime
) -> ItineraryPatch:
    """A4 nhờ đổi thứ tự lộ trình để cứu một lịch đặt, trước khi tính tới dời giờ."""

    itinerary = park.itinerary(guest_id)
    guest = park.guest(guest_id)
    clashing = [
        slot
        for slot in itinerary.slots
        if not slot.locked and slot.start < protect_end and slot.end > protect_start and slot.start >= now
    ]
    if not clashing:
        return ItineraryPatch(guest_id=guest_id)

    changes: list[ItineraryChange] = []
    for slot in clashing:
        service = park.service(slot.service_id)
        window = park.next_window_with_room(
            slot.service_id, after=protect_end, before=guest.leaves_at, party_size=1
        )
        if window is None or not is_allowed(park, service, guest.party, window):
            return ItineraryPatch(
                guest_id=guest_id,
                resolved=False,
                unresolved_reason=f"{service.name} không còn suất nào sau {protect_end:%H:%M} trước giờ khách về.",
            )
        changes.append(
            ItineraryChange(
                kind=ChangeKind.REORDERED,
                from_service_id=slot.service_id,
                from_service_name=slot.service_name,
                to_service_id=slot.service_id,
                to_service_name=slot.service_name,
                new_start=window,
                reason="Đổi thứ tự lộ trình để giữ nguyên giờ đã đặt bàn.",
            )
        )
    return ItineraryPatch(guest_id=guest_id, changes=tuple(changes))


def apply_patch(itinerary: Itinerary, patch: ItineraryPatch, park: MockPark) -> Itinerary:
    """Dựng bản lịch mới từ patch. Engine gọi sau khi governance đã cho qua."""

    updated = itinerary.model_copy(deep=True)
    for change in patch.changes:
        slot = updated.slot_for(change.from_service_id)
        if slot is None or slot.locked or change.new_start is None or change.to_service_id is None:
            continue
        service = park.service(change.to_service_id)
        slot.service_id = service.service_id
        slot.service_name = service.name
        slot.zone_id = service.zone_id
        slot.start = change.new_start
        slot.end = change.new_start + duration_of(service)
        slot.note = change.reason
    updated.slots.sort(key=lambda item: item.start)
    return updated


def touches_locked_slot(itinerary: Itinerary, patch: ItineraryPatch) -> bool:
    """Cờ để governance chặn đúng thứ mục 6 cấm, thay vì tin lời agent."""

    return any(
        (slot := itinerary.slot_for(change.from_service_id)) is not None and slot.locked
        for change in patch.changes
    )


def wait_answer(park: MockPark, service_id: str, *, now: datetime) -> WaitEstimate:
    """Trả lời tại chỗ, nêu đúng độ tin cậy của con số — không phán chắc nịch."""

    service = park.service(service_id)
    return WaitEstimate(
        service_id=service.service_id,
        service_name=service.name,
        minutes=park.wait_minutes(service_id),
        source=service.wait_source,
        measured_at=now,
    )
