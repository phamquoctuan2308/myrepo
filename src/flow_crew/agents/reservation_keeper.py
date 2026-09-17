"""A4 · Reservation Keeper — phục vụ khách hàng ⇄ đối tác.

Chủ động cứu lịch trước khi khách phát hiện xung đột. Thang xử lý ở mục 6 là
thứ tự bắt buộc, không phải gợi ý: nhờ A1 đổi thứ tự lộ trình trước → dời lịch
là phương án tiếp theo → huỷ là lựa chọn cuối cùng. `plan_rescue` chỉ leo lên
nấc sau khi nấc trước đã thực sự thất bại, và `RescuePlan` mang theo dấu vết
đó để governance kiểm được (POL-RES-02) thay vì tin lời agent.

Kênh liên hệ cũng theo thứ tự: hệ thống đặt bàn nếu outlet có, rồi tin nhắn,
cuối cùng mới gọi điện — và cuộc gọi phải tự giới thiệu là trợ lý tự động, xin
phép ghi âm, đọc mã đặt chỗ, tối đa 2 phút.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import Field

from src.flow_crew.contracts import FrozenContract, ItineraryPatch
from src.flow_crew.mock_park import (
    ContactChannel,
    MockPark,
    Reservation,
    ReservationStatus,
)

# Khách cần chừng này phút để đi từ hoạt động trước tới bàn ăn.
TRANSFER_BUFFER_MINUTES = 10
MAX_CALL_SECONDS = 120
MAX_CALLBACKS = 1
RESCHEDULE_STEP_MINUTES = 30


class RescueStep(StrEnum):
    NOTHING_TO_DO = "nothing_to_do"
    REORDER = "reorder"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"


RESCUE_STEP_NAMES: dict[RescueStep, str] = {
    RescueStep.NOTHING_TO_DO: "không cần can thiệp",
    RescueStep.REORDER: "đổi thứ tự lộ trình",
    RescueStep.RESCHEDULE: "dời giờ lịch đặt",
    RescueStep.CANCEL: "huỷ lịch đặt",
}


class RescuePlan(FrozenContract):
    reservation_id: str
    guest_id: str
    step: RescueStep
    reorder_patch: ItineraryPatch | None = None
    new_time: datetime | None = None
    channel: ContactChannel | None = None
    tried_reorder: bool = False
    tried_reschedule: bool = False
    reason: str = ""


class ConflictWindow(FrozenContract):
    reservation_id: str
    guest_id: str
    clash_service_id: str
    clash_service_name: str
    clash_start: datetime
    clash_end: datetime
    shortfall_minutes: int = Field(ge=1)


def conflicts_for(park: MockPark, guest_id: str, *, now: datetime) -> tuple[ConflictWindow, ...]:
    """Lịch đặt nào sắp cạn độ dư thời gian vì lịch trình vừa đổi."""

    found: list[ConflictWindow] = []
    itinerary = park.itinerary(guest_id)
    for reservation in park.reservations_of(guest_id):
        if reservation.status == ReservationStatus.CANCELLED or reservation.at < now:
            continue
        deadline = reservation.at - timedelta(minutes=TRANSFER_BUFFER_MINUTES)
        for slot in itinerary.slots:
            if slot.service_id == reservation.outlet_id or slot.end <= deadline or slot.start >= reservation.at:
                continue
            found.append(
                ConflictWindow(
                    reservation_id=reservation.reservation_id,
                    guest_id=guest_id,
                    clash_service_id=slot.service_id,
                    clash_service_name=slot.service_name,
                    clash_start=slot.start,
                    clash_end=slot.end,
                    shortfall_minutes=max(1, round((slot.end - deadline).total_seconds() / 60)),
                )
            )
            break
    return tuple(found)


def plan_rescue(
    park: MockPark,
    conflict: ConflictWindow,
    *,
    reorder_patch: ItineraryPatch,
    now: datetime,
) -> RescuePlan:
    """Leo thang đúng thứ tự: đổi lộ trình → dời giờ → huỷ.

    `reorder_patch` là câu trả lời A1 đã đưa cho yêu cầu đổi thứ tự — A4 không
    tự tính hộ lịch trình, đó là phạm vi của A1.
    """

    reservation = park.reservation(conflict.reservation_id)
    if reorder_patch.resolved and reorder_patch.changes:
        return RescuePlan(
            reservation_id=reservation.reservation_id,
            guest_id=reservation.guest_id,
            step=RescueStep.REORDER,
            reorder_patch=reorder_patch,
            tried_reorder=True,
            reason="Giữ nguyên giờ đã đặt bàn bằng cách đổi thứ tự lộ trình.",
        )

    new_time = _next_table_time(park, reservation, conflict)
    if new_time is not None:
        return RescuePlan(
            reservation_id=reservation.reservation_id,
            guest_id=reservation.guest_id,
            step=RescueStep.RESCHEDULE,
            new_time=new_time,
            channel=preferred_channel(park, reservation),
            tried_reorder=True,
            tried_reschedule=True,
            reason=f"Không đổi được lộ trình ({reorder_patch.unresolved_reason}); dời bàn sang {new_time:%H:%M}.",
        )

    return RescuePlan(
        reservation_id=reservation.reservation_id,
        guest_id=reservation.guest_id,
        step=RescueStep.CANCEL,
        channel=preferred_channel(park, reservation),
        tried_reorder=True,
        tried_reschedule=True,
        reason="Đã thử đổi lộ trình và dời giờ, không còn khung nào trước giờ khách về.",
    )


def _next_table_time(park: MockPark, reservation: Reservation, conflict: ConflictWindow) -> datetime | None:
    """Khung ăn gần nhất sau khi hoạt động xung đột kết thúc, trước giờ khách về."""

    guest = park.guest(reservation.guest_id)
    outlet = park.service(reservation.outlet_id)
    candidate = conflict.clash_end + timedelta(minutes=TRANSFER_BUFFER_MINUTES)
    minute_offset = (RESCHEDULE_STEP_MINUTES - candidate.minute % RESCHEDULE_STEP_MINUTES) % RESCHEDULE_STEP_MINUTES
    candidate += timedelta(minutes=minute_offset)
    latest = min(guest.leaves_at, outlet.closes_at)
    if candidate + timedelta(minutes=60) > latest:
        return None
    return candidate


def preferred_channel(park: MockPark, reservation: Reservation) -> ContactChannel:
    """Hệ thống đặt bàn nếu có, rồi tin nhắn, cuối cùng mới gọi điện."""

    outlet = park.service(reservation.outlet_id)
    if outlet.booking_system:
        return ContactChannel.BOOKING_SYSTEM
    if outlet.phone:
        return ContactChannel.PHONE
    return ContactChannel.SMS


def call_script(reservation: Reservation, new_time: datetime) -> tuple[str, ...]:
    """Kịch bản gọi đối tác. Mọi câu ở đây đều là điều kiện để governance cho qua."""

    return (
        "Xin chào, đây là trợ lý tự động của VinWonders Nha Trang, không phải nhân viên.",
        "Cuộc gọi được ghi âm để đối chiếu, mong anh/chị cho phép.",
        f"Tôi cần đổi giờ đặt bàn mã {reservation.confirmation_code}, {reservation.party_size} khách.",
        f"Từ {reservation.at:%H:%M} sang {new_time:%H:%M} hôm nay.",
        "Anh/chị xác nhận giúp tôi mã đặt chỗ và giờ mới ạ?",
    )


def call_params(reservation: Reservation, new_time: datetime) -> dict[str, object]:
    return {
        "outlet_id": reservation.outlet_id,
        "reservation_id": reservation.reservation_id,
        "confirmation_code": reservation.confirmation_code,
        "discloses_bot": True,
        "asks_recording_consent": True,
        "max_seconds": MAX_CALL_SECONDS,
        "max_callbacks": MAX_CALLBACKS,
        "script": list(call_script(reservation, new_time)),
    }


def guest_notice(reservation: Reservation, plan: RescuePlan) -> str:
    """Luôn báo lại kết quả kèm bằng chứng — không để yêu cầu của khách trôi đi."""

    if plan.step == RescueStep.REORDER:
        return (
            f"Bàn {reservation.outlet_name} {reservation.at:%H:%M} (mã {reservation.confirmation_code}) giữ nguyên. "
            "Mình đã đổi thứ tự lộ trình để anh/chị kịp giờ."
        )
    if plan.step == RescueStep.RESCHEDULE and plan.new_time is not None:
        return (
            f"Bàn {reservation.outlet_name} đã dời sang {plan.new_time:%H:%M} "
            f"(mã {reservation.confirmation_code}), nhà hàng đã xác nhận."
        )
    return (
        f"Bàn {reservation.outlet_name} {reservation.at:%H:%M} (mã {reservation.confirmation_code}) "
        "không còn khung nào phù hợp; mình xin phép huỷ giúp anh/chị."
    )
