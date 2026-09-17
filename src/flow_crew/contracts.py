"""Shared contract every FlowCrew agent speaks.

The charter's whole claim is a two-way loop: mật độ thật → hành động → đo lại.
These types are the joints of that loop. An agent never changes the park
directly — it emits a `ProposedAction`; governance answers with a
`GovernanceDecision`; anything a person must sign travels as an
`ApprovalTicket`. A5-style "AI decides" never appears, by construction.

Timestamps are simulation time (`src.flow_crew.clock`), never wall-clock time,
so a replayed park day produces the same audit trail.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrozenContract(BaseModel):
    """Immutable, strict base for everything an agent hands to another party."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StateModel(BaseModel):
    """Mutable workflow state; still rejects fields nobody declared."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AgentId(StrEnum):
    CREW_PM = "A0"
    GUEST_PLANNER = "A1"
    CROWD_ANALYST = "A2"
    OPS_DISPATCHER = "A3"
    RESERVATION_KEEPER = "A4"


AGENT_NAMES: dict[AgentId, str] = {
    AgentId.CREW_PM: "A0 · Crew PM",
    AgentId.GUEST_PLANNER: "A1 · Guest Planner",
    AgentId.CROWD_ANALYST: "A2 · Crowd Analyst",
    AgentId.OPS_DISPATCHER: "A3 · Ops Dispatcher",
    AgentId.RESERVATION_KEEPER: "A4 · Reservation Keeper",
}

# Mục 6: mỗi vai trò có thể chạy nhiều instance khi nhân rộng. PoC 6 tuần chạy
# đúng 1 instance mỗi vai — A0 vẫn route theo instance id để không phải viết lại
# khi tách A10/A11 theo vùng ở giai đoạn 3.
POC_INSTANCE_OF: dict[AgentId, str] = {agent: f"{agent.value}0" for agent in AgentId}


class HumanRole(StrEnum):
    SHIFT_LEAD = "shift_lead"
    MARKETING = "marketing"
    PARK_MANAGER = "park_manager"
    GUEST = "guest"


HUMAN_ROLE_NAMES: dict[HumanRole, str] = {
    HumanRole.SHIFT_LEAD: "Trưởng ca",
    HumanRole.MARKETING: "Marketing",
    HumanRole.PARK_MANAGER: "Quản lý công viên",
    HumanRole.GUEST: "Khách hàng",
}


def can_approve(actor: HumanRole, required: HumanRole) -> bool:
    """Who may sign what.

    Quản lý công viên bao trùm các quyết định vận hành — nhưng không ai ký thay
    khách hàng: dời hay huỷ lịch đặt của khách thì chỉ chính khách duyệt được.
    """

    if required == HumanRole.GUEST:
        return actor == HumanRole.GUEST
    if actor == HumanRole.GUEST:
        return False
    return actor == required or actor == HumanRole.PARK_MANAGER


class ActionType(StrEnum):
    # Rủi ro thấp, tự động
    POST_ROOM_MESSAGE = "post_room_message"
    NOTIFY_HUMAN = "notify_human"
    UPDATE_ITINERARY = "update_itinerary"
    HOLD_SLOT = "hold_slot"
    SEND_GUEST_MESSAGE = "send_guest_message"
    MEASURE_IMPACT = "measure_impact"
    CALL_PARTNER = "call_partner"
    # Chạm tới vận hành hoặc tới khách — luôn qua người duyệt
    OPEN_EXTRA_LANE = "open_extra_lane"
    REASSIGN_STAFF = "reassign_staff"
    REROUTE_GUESTS = "reroute_guests"
    PUSH_PROMOTION = "push_promotion"
    GRANT_FAST_PASS = "grant_fast_pass"
    RESCHEDULE_RESERVATION = "reschedule_reservation"
    CANCEL_RESERVATION = "cancel_reservation"


class ProposedAction(FrozenContract):
    """Something an agent wants done. It has no effect until it is executed."""

    action_id: str = Field(min_length=1, max_length=32)
    workflow_id: str = Field(min_length=1, max_length=32)
    proposed_by: AgentId
    action_type: ActionType
    summary: str = Field(min_length=1, max_length=500)
    params: dict[str, Any] = Field(default_factory=dict)
    affected_guests: int = Field(default=0, ge=0)
    estimated_cost_vnd: int = Field(default=0, ge=0)


class Verdict(StrEnum):
    PASS = "PASS"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


class GovernanceDecision(FrozenContract):
    action_id: str
    verdict: Verdict
    approver_role: HumanRole | None = None
    policy_codes: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


# ---- A2 · bức tranh mật độ ----------------------------------------------------


class DensityLevel(StrEnum):
    CALM = "calm"
    BUSY = "busy"
    CROWDED = "crowded"
    OVERLOAD = "overload"


DENSITY_LEVEL_NAMES: dict[DensityLevel, str] = {
    DensityLevel.CALM: "vắng",
    DensityLevel.BUSY: "bình thường",
    DensityLevel.CROWDED: "đông",
    DensityLevel.OVERLOAD: "quá tải",
}


class WaitSource(StrEnum):
    """Độ tin cậy của thời gian chờ — A1 phải nói rõ, không đưa số chắc nịch."""

    CAMERA = "camera"
    ESTIMATE = "estimate"


class ZoneDensity(FrozenContract):
    zone_id: str
    zone_name: str
    headcount: int = Field(ge=0)
    capacity: int = Field(gt=0)
    load_pct: float = Field(ge=0)
    level: DensityLevel
    trend_pct_per_10min: float
    hottest_service_id: str | None = None


class WaitEstimate(FrozenContract):
    service_id: str
    service_name: str
    minutes: int = Field(ge=0)
    source: WaitSource
    measured_at: datetime

    @property
    def phrasing(self) -> str:
        if self.source == WaitSource.CAMERA:
            return f"~{self.minutes} phút (đo bằng camera lúc {self.measured_at:%H:%M})"
        return f"khoảng {self.minutes} phút (ước lượng, chưa đo được bằng camera)"


class AlertCause(StrEnum):
    SERVICE_CLOSED = "service_closed"
    SHOW_ENDED = "show_ended"
    RAIN = "rain"
    PARK_LOAD_RISING = "park_load_rising"


ALERT_CAUSE_NAMES: dict[AlertCause, str] = {
    AlertCause.SERVICE_CLOSED: "một dịch vụ trong khu đóng đột xuất",
    AlertCause.SHOW_ENDED: "show vừa kết thúc, khách rời cùng lúc",
    AlertCause.RAIN: "mưa, khách dồn vào khu có mái",
    AlertCause.PARK_LOAD_RISING: "tải toàn công viên đang tăng",
}


class CrowdAlert(FrozenContract):
    """A2 chỉ mô tả và xếp hạng. Không kèm khuyến nghị — đó là việc của A3."""

    alert_id: str
    raised_at: datetime
    zone_id: str
    zone_name: str
    service_id: str | None = None
    service_name: str | None = None
    level: DensityLevel
    load_pct: float = Field(ge=0)
    threshold_pct: float = Field(gt=0)
    minutes_to_overload: int | None = Field(default=None, ge=0)
    guests_heading: int = Field(ge=0)
    cause: AlertCause
    severity_score: float = Field(ge=0)
    rank: int = Field(ge=1)

    @property
    def headline(self) -> str:
        window = (
            f"quá tải trong {self.minutes_to_overload} phút"
            if self.minutes_to_overload
            else "đã quá tải"
        )
        because = f" · {ALERT_CAUSE_NAMES[self.cause]}" if self.cause else ""
        return f"{self.zone_name}: {self.load_pct:.0f}% tải (ngưỡng {self.threshold_pct:.0f}%) — {window}{because}"


class ImpactMeasurement(FrozenContract):
    """A3 đo lại sau can thiệp, A2 xác nhận — khép vòng đo lường."""

    alert_id: str
    measured_at: datetime
    load_pct_before: float = Field(ge=0)
    load_pct_after: float = Field(ge=0)
    guests_rerouted: int = Field(ge=0)
    confirmed_by_analyst: bool = False

    @property
    def delta_pct(self) -> float:
        return round(self.load_pct_after - self.load_pct_before, 1)


# ---- A1 · lịch trình khách ----------------------------------------------------


class ItinerarySlot(StateModel):
    service_id: str
    service_name: str
    zone_id: str
    start: datetime
    end: datetime
    locked: bool = False
    note: str = ""


class Itinerary(StateModel):
    guest_id: str
    slots: list[ItinerarySlot] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)

    def slot_for(self, service_id: str) -> ItinerarySlot | None:
        return next((slot for slot in self.slots if slot.service_id == service_id), None)


class ChangeKind(StrEnum):
    REPLACED = "replaced"
    MOVED = "moved"
    REORDERED = "reordered"
    DROPPED = "dropped"


CHANGE_KIND_NAMES: dict[ChangeKind, str] = {
    ChangeKind.REPLACED: "đổi sang dịch vụ khác",
    ChangeKind.MOVED: "dời giờ",
    ChangeKind.REORDERED: "đổi thứ tự lộ trình",
    ChangeKind.DROPPED: "bỏ khỏi lịch",
}


class ItineraryChange(FrozenContract):
    kind: ChangeKind
    from_service_id: str
    from_service_name: str
    to_service_id: str | None = None
    to_service_name: str | None = None
    new_start: datetime | None = None
    reason: str = ""


class ItineraryPatch(FrozenContract):
    """Chỉ phần thay đổi — không bao giờ gửi lại lịch mới hoàn toàn."""

    guest_id: str
    changes: tuple[ItineraryChange, ...] = ()
    resolved: bool = True
    unresolved_reason: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.changes


# ---- A3 · gói can thiệp -------------------------------------------------------


class InterventionOption(FrozenContract):
    """Một phương án, kèm tác động ước tính — xếp từ chi phí thấp đến cao."""

    option_id: str
    alert_id: str
    action_type: ActionType
    summary: str
    params: dict[str, Any] = Field(default_factory=dict)
    affected_guests: int = Field(gt=0)  # mục 6: không đề xuất mơ hồ
    estimated_wait_delta_minutes: int
    estimated_cost_vnd: int = Field(ge=0)
    approver_role: HumanRole


# ---- Phê duyệt ----------------------------------------------------------------


class TicketKind(StrEnum):
    INTERVENTION = "intervention"
    RESERVATION_CHANGE = "reservation_change"


class TicketStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalTicket(StateModel):
    """One 1-click decision for one person; covers every action in its package."""

    ticket_id: str
    workflow_id: str
    kind: TicketKind
    title: str
    urgent: bool = False
    required_role: HumanRole
    actions: tuple[ProposedAction, ...]
    decisions: tuple[GovernanceDecision, ...]
    guest_message_preview: str | None = None
    status: TicketStatus = TicketStatus.PENDING
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    decided_role: HumanRole | None = None
    note: str = ""

    @property
    def action_ids(self) -> frozenset[str]:
        return frozenset(action.action_id for action in self.actions)


# ---- Phòng chung & dòng thời gian ---------------------------------------------


class RoomMessage(FrozenContract):
    """US-2: một phòng chung, @mention route đúng người, không ai kể lại từ đầu."""

    seq: int = Field(ge=1)
    at: datetime
    author: str
    mentions: tuple[str, ...] = ()
    text: str = Field(min_length=1)


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    CLOSED = "closed"


class WorkflowStep(FrozenContract):
    """US-5 live trace: một dòng người vận hành đọc được; audit log là bản đầy đủ."""

    seq: int = Field(ge=1)
    at: datetime
    actor: str
    kind: str
    title: str
    detail: str = ""


class CrowdWorkflow(StateModel):
    workflow_id: str
    kind: str = "crowd_incident"
    status: WorkflowStatus = WorkflowStatus.RUNNING
    created_at: datetime
    closed_at: datetime | None = None
    alert: CrowdAlert
    options: tuple[InterventionOption, ...] = ()
    ticket_ids: list[str] = Field(default_factory=list)
    replanned_guest_ids: list[str] = Field(default_factory=list)
    unresolved_guest_ids: list[str] = Field(default_factory=list)
    rescued_reservation_ids: list[str] = Field(default_factory=list)
    measurement: ImpactMeasurement | None = None
    waiting_for: list[str] = Field(default_factory=list)
    steps: list[WorkflowStep] = Field(default_factory=list)
