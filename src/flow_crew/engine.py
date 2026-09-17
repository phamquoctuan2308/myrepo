"""FlowCrew engine — nơi vòng lặp hai chiều của charter thực sự khép lại.

Engine giữ trạng thái chung và là đường duy nhất chạm vào công viên. Hai tính
chất đáng nói, cả hai đều là thuộc tính của code chứ không phải lời hứa:

* `execute` hỏi lại `PolicyGate` đúng lúc thực thi, không tin phán quyết lúc đề
  xuất. Giữa lúc A3 soạn phương án lúc 14:08 và lúc Trưởng ca bấm duyệt lúc
  14:10, hạn mức fast-pass của ca có thể đã bị tiêu bởi việc khác — một chữ ký
  không được phép làm sống lại hành động mà trạng thái hiện tại đã cấm;
* mỗi vai chỉ làm đúng việc của mình. Agent trả về kế hoạch, engine mới ghi;
  nên 40 lượt khách được xếp chỗ tuần tự và không ai phát trùng suất của ai.

Hero flow mục 7 chạy đúng sáu giai đoạn của khuôn cAI Workspace: giao mục tiêu
→ bot điều phối → handoff → bot chạy tác vụ (live trace) → cổng phê duyệt →
kết quả + audit. Khác biệt duy nhất: mục tiêu do A2 phát hiện và đưa vào phòng
chung, thay vì một nhân viên gõ tay.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, TypeVar

from src.flow_crew.agents import (
    crew_pm,
    crowd_analyst,
    guest_planner,
    ops_dispatcher,
    reservation_keeper,
)
from src.flow_crew.approvals import ApprovalQueue
from src.flow_crew.audit import AuditLog
from src.flow_crew.clock import SimClock, hhmm
from src.flow_crew.contracts import (
    AGENT_NAMES,
    HUMAN_ROLE_NAMES,
    ActionType,
    AgentId,
    ApprovalTicket,
    CrowdAlert,
    CrowdWorkflow,
    GovernanceDecision,
    HumanRole,
    ImpactMeasurement,
    InterventionOption,
    ItineraryPatch,
    ProposedAction,
    RoomMessage,
    TicketKind,
    TicketStatus,
    Verdict,
    WorkflowStatus,
    WorkflowStep,
    can_approve,
)
from src.flow_crew.governance import POLICIES, PolicyGate
from src.flow_crew.mock_park import (
    FAST_PASS_SHIFT_CAP,
    MockPark,
    ServiceStatus,
    ToolUnavailableError,
)

TOOL_MAX_ATTEMPTS = 2
# Khoảng chờ trước khi đo lại hiệu quả can thiệp (mục 6 · A3).
MEASURE_AFTER_MINUTES = 18

T = TypeVar("T")


class WorkflowNotFoundError(LookupError):
    pass


class GovernanceBlockedError(RuntimeError):
    pass


class ApprovalBypassError(RuntimeError):
    pass


class IncidentStateError(RuntimeError):
    pass


@dataclass
class EngineMetrics:
    handoffs: int = 0
    auto_executed: int = 0
    executed_with_approval: int = 0
    blocked_actions: int = 0
    bypass_attempts_blocked: int = 0
    tool_retries: int = 0
    guests_replanned: int = 0
    guests_unresolved: int = 0
    reservations_rescued: int = 0


@dataclass
class DirectAnswer:
    """US-1: câu trả lời của một agent khi bị hỏi thẳng, không cần chuỗi sự cố."""

    agent: AgentId
    text: str
    data: dict[str, Any] = field(default_factory=dict)


class FlowCrewEngine:
    def __init__(self, *, park: MockPark | None = None, clock: SimClock | None = None) -> None:
        self.park = park or MockPark()
        self.clock = clock or SimClock()
        self.gate = PolicyGate(self.park)
        self.approvals = ApprovalQueue()
        self.audit = AuditLog()
        self.metrics = EngineMetrics()
        self.workflows: dict[str, CrowdWorkflow] = {}
        self.room: list[RoomMessage] = []
        self._action_seq = 0
        self._workflow_seq = 0
        self._pending_conflicts: dict[str, tuple[str, str, datetime]] = {}
        # Giữ chỗ đã thực hiện, khoá theo (action, mục lịch). `_apply` không
        # nguyên tử: nếu hệ thống app lỗi sau khi suất đã được giữ, lần thử lại
        # phải ghi tiếp chứ không được giữ chỗ lần thứ hai.
        self._seats_taken: set[tuple[str, str]] = set()

    # ---- cổng thực thi duy nhất ---------------------------------------------

    def execute(self, action: ProposedAction, *, ticket: ApprovalTicket | None = None) -> GovernanceDecision:
        """Đường duy nhất để bất cứ thứ gì chạm vào công viên."""

        workflow = self.workflows.get(action.workflow_id)
        decision = self.gate.evaluate(action)

        if decision.verdict == Verdict.BLOCK:
            self.metrics.blocked_actions += 1
            self._audit(
                workflow,
                action.proposed_by.value,
                "action.blocked",
                "; ".join(decision.reasons),
                action_id=action.action_id,
                policy_codes=list(decision.policy_codes),
            )
            raise GovernanceBlockedError("; ".join(decision.reasons))

        if decision.verdict == Verdict.REQUIRE_APPROVAL:
            signed = (
                ticket is not None
                and ticket.workflow_id == action.workflow_id
                and ticket.status == TicketStatus.APPROVED
                and action.action_id in ticket.action_ids
                and ticket.decided_role is not None
                and decision.approver_role is not None
                and can_approve(ticket.decided_role, decision.approver_role)
            )
            if not signed:
                self.metrics.bypass_attempts_blocked += 1
                self._audit(
                    workflow,
                    action.proposed_by.value,
                    "action.bypass_blocked",
                    f"{action.action_type.value} cần {decision.approver_role} duyệt trước khi thực hiện",
                    action_id=action.action_id,
                )
                raise ApprovalBypassError(f"{action.summary}: chưa có phê duyệt hợp lệ")

        self._apply(action)
        if decision.verdict == Verdict.REQUIRE_APPROVAL:
            self.metrics.executed_with_approval += 1
        else:
            self.metrics.auto_executed += 1
        self._audit(
            workflow,
            action.proposed_by.value,
            "action.executed",
            action.summary,
            action_id=action.action_id,
            action_type=action.action_type.value,
            verdict=decision.verdict.value,
            policy_codes=list(decision.policy_codes),
            ticket_id=ticket.ticket_id if ticket is not None else None,
        )
        return decision

    def _apply(self, action: ProposedAction) -> None:
        params = action.params
        now = self.clock.now
        match action.action_type:
            case ActionType.POST_ROOM_MESSAGE:
                self.room.append(
                    RoomMessage(
                        seq=len(self.room) + 1,
                        at=now,
                        author=str(params.get("author", AGENT_NAMES[action.proposed_by])),
                        mentions=tuple(str(item) for item in params.get("mentions", ())),
                        text=str(params["text"]),
                    )
                )
            case ActionType.NOTIFY_HUMAN:
                self.room.append(
                    RoomMessage(
                        seq=len(self.room) + 1,
                        at=now,
                        author=AGENT_NAMES[action.proposed_by],
                        mentions=(HUMAN_ROLE_NAMES[HumanRole(str(params["role"]))],),
                        text=str(params["message"]),
                    )
                )
            case ActionType.UPDATE_ITINERARY:
                patch: ItineraryPatch = params["patch"]
                itinerary = self.park.itinerary(patch.guest_id)
                for change in patch.changes:
                    if not change.to_service_id or not change.new_start:
                        continue
                    seat = (action.action_id, change.from_service_id)
                    if seat in self._seats_taken:
                        continue
                    slot = itinerary.slot_for(change.from_service_id)
                    self.park.book_slot(change.to_service_id, change.new_start, 1)
                    if slot is not None and (
                        slot.service_id != change.to_service_id or slot.start != change.new_start
                    ):
                        self.park.release_slot(slot.service_id, slot.start, 1)
                    self._seats_taken.add(seat)
                self.park.apply_itinerary(guest_planner.apply_patch(itinerary, patch, self.park))
            case ActionType.HOLD_SLOT:
                self.park.book_slot(str(params["service_id"]), params["window"], int(params.get("seats", 1)))
            case ActionType.SEND_GUEST_MESSAGE:
                self.park.send_guest_message(str(params["guest_id"]), str(params["text"]), at_time=now)
            case ActionType.MEASURE_IMPACT:
                pass  # chỉ đọc; kết quả đã nằm trong ImpactMeasurement của A3
            case ActionType.OPEN_EXTRA_LANE:
                self.park.open_extra_lane(str(params["service_id"]))
            case ActionType.REASSIGN_STAFF:
                pass  # PoC chưa mô phỏng bảng phân ca; hành động vẫn đi qua đúng cổng duyệt
            case ActionType.REROUTE_GUESTS:
                self.park.reroute_guests(
                    from_service_id=str(params["from_service_id"]),
                    to_service_id=str(params["service_id"]),
                    headcount=int(params["headcount"]),
                )
            case ActionType.PUSH_PROMOTION:
                self.park.push_promotion(
                    promotion_id=action.action_id,
                    outlet_id=str(params["service_id"]),
                    audience=int(params["audience"]),
                    at_time=now,
                )
                self.park.reroute_guests(
                    from_service_id=str(params["from_service_id"]),
                    to_service_id=str(params["service_id"]),
                    headcount=int(params["audience"]) // 4,
                )
            case ActionType.GRANT_FAST_PASS:
                self.park.grant_fast_pass(
                    tuple(str(item) for item in params["guest_ids"]), str(params["service_id"])
                )
            case ActionType.CALL_PARTNER:
                reservation = self.park.reservation(str(params["reservation_id"]))
                outcome = self.park.call_partner(
                    str(params["outlet_id"]),
                    tuple(str(line) for line in params["script"]),
                    seconds=int(params.get("seconds", 95)),
                    reached=bool(params.get("reached", True)),
                )
                reservation.evidence.append(
                    f"Gọi {reservation.outlet_name} lúc {hhmm(now)} · {outcome.duration_seconds}s · "
                    f"{'xác nhận' if outcome.reached else 'không nghe máy, chuyển nhân viên thật'}"
                )
            case ActionType.RESCHEDULE_RESERVATION:
                self.park.move_reservation(str(params["reservation_id"]), params["new_time"])
            case ActionType.CANCEL_RESERVATION:
                self.park.cancel_reservation(str(params["reservation_id"]))

    # ---- US-1 · hỏi thẳng từng agent ----------------------------------------

    def ask(self, agent: AgentId, question: str, *, guest_id: str | None = None) -> DirectAnswer:
        """Mỗi agent trả lời được ngay khi bị hỏi, không cần chờ đúng thứ tự trong chuỗi."""

        now = self.clock.now
        self.audit.record(at=now, actor=agent.value, event="chat.direct", detail=question)
        match agent:
            case AgentId.CREW_PM:
                return self._ask_crew_pm(question)
            case AgentId.CROWD_ANALYST:
                return self._ask_analyst(question)
            case AgentId.GUEST_PLANNER:
                return self._ask_planner(question, guest_id)
            case AgentId.OPS_DISPATCHER:
                return self._ask_dispatcher()
            case AgentId.RESERVATION_KEEPER:
                return self._ask_keeper(guest_id)
        raise ValueError(f"Không có agent {agent}")

    def _ask_crew_pm(self, question: str) -> DirectAnswer:
        """A0 tự hỏi các agent liên quan rồi tổng hợp, ghi rõ ai nói gì."""

        routing = crew_pm.route(question)
        lines: list[crew_pm.ReportLine] = []
        # Chuyển nguyên câu hỏi xuống A2 thay vì tự tóm tắt: admin hỏi đích danh
        # một khu thì phải nhận đúng số của khu đó.
        lines.append(crew_pm.ReportLine(agent=AgentId.CROWD_ANALYST, text=self._ask_analyst(question).text))
        alerts = crowd_analyst.detect_alerts(self.park, now=self.clock.now)
        if alerts:
            options = ops_dispatcher.build_package(
                self.park,
                alert=alerts[0],
                congested_zone_ids=frozenset(alert.zone_id for alert in alerts),
            )
            summary = (
                f"Có {len(options)} phương án sẵn cho {alerts[0].zone_name}, rẻ nhất: {options[0].summary}."
                if options
                else "Chưa có phương án nào cần trình duyệt."
            )
            lines.append(crew_pm.ReportLine(agent=AgentId.OPS_DISPATCHER, text=summary))
        else:
            lines.append(
                crew_pm.ReportLine(agent=AgentId.OPS_DISPATCHER, text="Chưa có khu nào vượt ngưỡng cần can thiệp.")
            )
        pending = self.approvals.pending()
        lines.append(
            crew_pm.ReportLine(
                agent=AgentId.RESERVATION_KEEPER,
                text=f"{len(self.park.calls)} cuộc gọi đối tác đã thực hiện hôm nay; "
                f"{len(pending)} yêu cầu đang chờ duyệt.",
            )
        )
        return DirectAnswer(
            agent=AgentId.CREW_PM,
            text=crew_pm.summarise(tuple(lines)),
            data={"routed_to": routing.agent.value, "instance": routing.instance_id, "reason": routing.reason},
        )

    def _ask_analyst(self, question: str) -> DirectAnswer:
        picture = crowd_analyst.zone_picture(self.park)
        asked = next((zone for zone in picture if zone.zone_name.lower() in question.lower()), None)
        zones = (asked,) if asked else picture[:3]
        text = "\n".join(
            f"{zone.zone_name}: {zone.load_pct:.0f}% tải, {zone.headcount} khách, "
            f"đà {zone.trend_pct_per_10min:+.1f}%/10 phút."
            for zone in zones
        )
        return DirectAnswer(agent=AgentId.CROWD_ANALYST, text=text, data={"zones": [zone.zone_id for zone in zones]})

    def _ask_planner(self, question: str, guest_id: str | None) -> DirectAnswer:
        target = guest_id or next(iter(self.park.guests))
        itinerary = guest_planner.build_itinerary(self.park, target, now=self.clock.now)
        lines = [
            f"{hhmm(slot.start)}–{hhmm(slot.end)} · {slot.service_name} "
            f"({guest_planner.wait_answer(self.park, slot.service_id, now=self.clock.now).phrasing})"
            for slot in itinerary.slots
        ]
        return DirectAnswer(
            agent=AgentId.GUEST_PLANNER,
            text="\n".join(lines) or "Chưa còn dịch vụ nào phù hợp trong khung giờ của anh/chị.",
            data={"guest_id": target, "slots": len(itinerary.slots)},
        )

    def _ask_dispatcher(self) -> DirectAnswer:
        alerts = crowd_analyst.detect_alerts(self.park, now=self.clock.now)
        if not alerts:
            return DirectAnswer(agent=AgentId.OPS_DISPATCHER, text="Chưa khu nào vượt ngưỡng; không có gì cần duyệt.")
        congested = frozenset(alert.zone_id for alert in alerts)
        blocks: list[str] = []
        for alert in alerts:
            options = ops_dispatcher.build_package(self.park, alert=alert, congested_zone_ids=congested)
            listed = "\n".join(
                f"  · {option.summary} — {option.affected_guests} khách, "
                f"{option.estimated_wait_delta_minutes:+d} phút chờ, "
                f"{option.estimated_cost_vnd:,}đ, cần {HUMAN_ROLE_NAMES[option.approver_role]} duyệt"
                for option in options
            )
            blocks.append(f"#{alert.rank} {alert.headline}\n{listed}")
        return DirectAnswer(
            agent=AgentId.OPS_DISPATCHER, text="\n".join(blocks), data={"alerts": len(alerts)}
        )

    def _ask_keeper(self, guest_id: str | None) -> DirectAnswer:
        target = guest_id or next(iter(self.park.guests))
        conflicts = reservation_keeper.conflicts_for(self.park, target, now=self.clock.now)
        if not conflicts:
            bookings = self.park.reservations_of(target)
            if not bookings:
                return DirectAnswer(agent=AgentId.RESERVATION_KEEPER, text="Anh/chị chưa có lịch đặt nào hôm nay.")
            listed = ", ".join(f"{item.outlet_name} {hhmm(item.at)} (mã {item.confirmation_code})" for item in bookings)
            return DirectAnswer(
                agent=AgentId.RESERVATION_KEEPER,
                text=f"Lịch đặt của anh/chị vẫn đủ thời gian: {listed}.",
                data={"guest_id": target},
            )
        conflict = conflicts[0]
        return DirectAnswer(
            agent=AgentId.RESERVATION_KEEPER,
            text=f"{conflict.clash_service_name} kết thúc {hhmm(conflict.clash_end)}, "
            f"trễ {conflict.shortfall_minutes} phút so với giờ bàn. Mình thử đổi thứ tự lộ trình trước.",
            data={"guest_id": target, "reservation_id": conflict.reservation_id},
        )

    # ---- Hero flow · giai đoạn 1: A2 phát hiện và giao mục tiêu ---------------

    def open_incident(self, *, closed_service_id: str = "SW-DOLPHIN") -> CrowdWorkflow:
        """14:05 — một dịch vụ đóng đột xuất; A2 đưa mục tiêu vào phòng chung."""

        now = self.clock.now
        if self.park.service(closed_service_id).status is ServiceStatus.CLOSED:
            raise IncidentStateError(f"{self.park.service(closed_service_id).name} đã đóng; sự cố này đang được xử lý")
        self.park.close_service(closed_service_id, now)
        alerts = crowd_analyst.detect_alerts(self.park, now=now)
        if not alerts:
            raise RuntimeError("Không có cảnh báo nào để mở workflow")
        alert = alerts[0]

        self._workflow_seq += 1
        workflow = CrowdWorkflow(
            workflow_id=f"WF-{self._workflow_seq:04d}",
            created_at=now,
            alert=alert,
        )
        self.workflows[workflow.workflow_id] = workflow
        self._audit(
            workflow,
            AgentId.CROWD_ANALYST.value,
            "alert.raised",
            alert.headline,
            alert_id=alert.alert_id,
            zone_id=alert.zone_id,
            load_pct=alert.load_pct,
            guests_heading=alert.guests_heading,
            severity=alert.severity_score,
            other_zones=[other.zone_name for other in alerts[1:]],
        )
        self._step(workflow, AgentId.CROWD_ANALYST.value, "goal", "Giao mục tiêu vào phòng chung", alert.headline)
        also = (
            f" Khu {alerts[1].zone_name} cũng sẽ chạm ngưỡng trong {alerts[1].minutes_to_overload} phút."
            if len(alerts) > 1
            else ""
        )
        self._act(
            workflow,
            AgentId.CROWD_ANALYST,
            ActionType.POST_ROOM_MESSAGE,
            f"Cảnh báo {alert.zone_name}",
            {
                "text": f"{alert.headline}. {alert.guests_heading} khách đang có "
                f"{alert.service_name} trong lịch trình.{also}",
                "mentions": [AGENT_NAMES[AgentId.CREW_PM]],
            },
        )
        self._replan_guests(workflow)
        self._prepare_interventions(workflow, alerts)
        return workflow

    # ---- giai đoạn 2: A0 → A1, tính lại lịch trình --------------------------

    def _replan_guests(self, workflow: CrowdWorkflow) -> None:
        """14:07 — A0 xác định A1 là agent đúng để nhận việc, bàn giao kèm ngữ cảnh."""

        alert = workflow.alert
        routing = self._handoff(
            workflow, AgentId.CROWD_ANALYST, "cập nhật lịch trình cho khách bị ảnh hưởng"
        )
        if routing.agent is not AgentId.GUEST_PLANNER:  # pragma: no cover - bảng năng lực đã cố định
            raise RuntimeError(f"A0 định tuyến sai: {routing.agent}")

        self.clock.advance(2)
        assert alert.service_id is not None
        for guest_id in self.park.guest_ids_heading_to(alert.service_id, after=workflow.created_at):
            patch = guest_planner.replan(self.park, guest_id, alert=alert, now=self.clock.now)
            if not patch.resolved or not patch.changes:
                workflow.unresolved_guest_ids.append(guest_id)
                self.metrics.guests_unresolved += 1
                continue
            self._write_itinerary(workflow, guest_id, patch)
            workflow.replanned_guest_ids.append(guest_id)
            self.metrics.guests_replanned += 1

        self._step(
            workflow,
            AgentId.GUEST_PLANNER.value,
            "replan",
            f"Tính lại lịch cho {alert.guests_heading} lượt khách",
            f"{len(workflow.replanned_guest_ids)} lượt có phương án tốt ngay, "
            f"{len(workflow.unresolved_guest_ids)} lượt thì không.",
        )
        self._act(
            workflow,
            AgentId.GUEST_PLANNER,
            ActionType.POST_ROOM_MESSAGE,
            "Kết quả tính lại lịch trình",
            {
                "text": f"{len(workflow.replanned_guest_ids)}/{alert.guests_heading} lượt khách đã có phương án "
                f"thay thế gần đó. Còn {len(workflow.unresolved_guest_ids)} lượt không còn suất phù hợp.",
                "mentions": [AGENT_NAMES[AgentId.OPS_DISPATCHER]],
            },
        )

    def _write_itinerary(self, workflow: CrowdWorkflow, guest_id: str, patch: ItineraryPatch) -> None:
        """Ghi patch vào lịch của đúng khách đang đối thoại, rồi báo phần thay đổi."""

        itinerary = self.park.itinerary(guest_id)
        action = self._new_action(
            workflow,
            AgentId.GUEST_PLANNER,
            ActionType.UPDATE_ITINERARY,
            f"Cập nhật lịch trình {guest_id}",
            {
                "guest_id": guest_id,
                "speaking_with": guest_id,
                "patch": patch,
                "touches_locked_slot": guest_planner.touches_locked_slot(itinerary, patch),
            },
        )
        self._run(workflow, AgentId.GUEST_PLANNER, action)
        for change in patch.changes:
            when = f" Giờ mới: {hhmm(change.new_start)}." if change.new_start else ""
            self._act(
                workflow,
                AgentId.GUEST_PLANNER,
                ActionType.SEND_GUEST_MESSAGE,
                f"Báo thay đổi cho {guest_id}",
                {
                    "guest_id": guest_id,
                    "text": f"{change.reason}{when} Phần còn lại của lịch giữ nguyên.",
                },
            )

    # ---- giai đoạn 3-4: A1 → A3, gói can thiệp + cổng duyệt -------------------

    def _prepare_interventions(self, workflow: CrowdWorkflow, alerts: tuple[CrowdAlert, ...]) -> None:
        """14:08–14:10 — A3 chuẩn bị phương án, mỗi gói chờ đúng người duyệt."""

        self._handoff(workflow, AgentId.GUEST_PLANNER, "chuẩn bị phương án can thiệp cho vận hành")
        self.clock.advance(1)
        options = ops_dispatcher.build_package(
            self.park,
            alert=workflow.alert,
            unresolved_guest_ids=tuple(workflow.unresolved_guest_ids),
            congested_zone_ids=frozenset(alert.zone_id for alert in alerts),
        )
        workflow.options = options
        for option in options:
            self._step(
                workflow,
                AgentId.OPS_DISPATCHER.value,
                "option",
                option.summary,
                f"{option.affected_guests} khách · {option.estimated_wait_delta_minutes:+d} phút chờ · "
                f"{option.estimated_cost_vnd:,}đ · cần {HUMAN_ROLE_NAMES[option.approver_role]} duyệt",
            )
            self._open_ticket(workflow, option)

        self.clock.advance(2)
        workflow.status = WorkflowStatus.WAITING_HUMAN
        workflow.waiting_for = [
            HUMAN_ROLE_NAMES[self.approvals.get(ticket_id).required_role] for ticket_id in workflow.ticket_ids
        ]
        self._act(
            workflow,
            AgentId.OPS_DISPATCHER,
            ActionType.POST_ROOM_MESSAGE,
            "Trình gói can thiệp",
            {
                "text": f"{len(options)} phương án đã sẵn sàng, xếp từ rẻ đến đắt. "
                f"Chờ duyệt song song: {', '.join(workflow.waiting_for)}.",
                "mentions": workflow.waiting_for,
            },
        )

    def _open_ticket(self, workflow: CrowdWorkflow, option: InterventionOption) -> ApprovalTicket:
        action = self._new_action(
            workflow,
            AgentId.OPS_DISPATCHER,
            option.action_type,
            option.summary,
            dict(option.params),
            affected_guests=option.affected_guests,
            cost_vnd=option.estimated_cost_vnd,
        )
        return self._file_for_approval(
            workflow, action, kind=TicketKind.INTERVENTION, title=option.summary, urgent=workflow.alert.rank == 1
        )

    def _file_for_approval(
        self,
        workflow: CrowdWorkflow,
        action: ProposedAction,
        *,
        kind: TicketKind,
        title: str,
        urgent: bool = False,
        preview: str | None = None,
    ) -> ApprovalTicket:
        decision = self.gate.evaluate(action)
        self._audit(
            workflow,
            "policy_gate",
            "governance.decision",
            decision.verdict.value,
            action_id=action.action_id,
            verdict=decision.verdict.value,
            approver_role=decision.approver_role.value if decision.approver_role else None,
            policy_codes=list(decision.policy_codes),
        )
        if decision.verdict == Verdict.BLOCK:
            self.metrics.blocked_actions += 1
            self._step(workflow, "policy_gate", "blocked", f"BLOCK · {title}", "; ".join(decision.reasons))
            raise GovernanceBlockedError("; ".join(decision.reasons))

        ticket = self.approvals.open(
            workflow_id=workflow.workflow_id,
            kind=kind,
            title=title,
            actions=(action,),
            decisions=(decision,),
            at=self.clock.now,
            urgent=urgent,
            guest_message_preview=preview,
        )
        workflow.ticket_ids.append(ticket.ticket_id)
        self._step(
            workflow,
            "policy_gate",
            "approval_request",
            f"Cần {HUMAN_ROLE_NAMES[ticket.required_role]} duyệt · {ticket.ticket_id}",
            f"{title}. Căn cứ: {', '.join(decision.policy_codes)}.",
        )
        self._audit(
            workflow,
            "policy_gate",
            "approval.requested",
            title,
            ticket_id=ticket.ticket_id,
            required_role=ticket.required_role.value,
            policy_codes=list(decision.policy_codes),
        )
        return ticket

    # ---- giai đoạn 5: con người quyết ----------------------------------------

    def decide(
        self,
        ticket_id: str,
        *,
        role: HumanRole,
        actor_name: str,
        approved: bool,
        note: str = "",
    ) -> ApprovalTicket:
        """Một chữ ký. Sau đó engine mới chạy tiếp — không sớm hơn một giây nào."""

        ticket = self.approvals.decide(
            ticket_id, role=role, actor_name=actor_name, approved=approved, at=self.clock.now, note=note
        )
        workflow = self.workflows[ticket.workflow_id]
        self._audit(
            workflow,
            actor_name,
            "approval.decided",
            f"{'Duyệt' if approved else 'Từ chối'} {ticket_id}",
            ticket_id=ticket_id,
            role=role.value,
            note=note,
        )
        self._step(
            workflow,
            actor_name,
            "approval",
            f"{HUMAN_ROLE_NAMES[role]} {'duyệt' if approved else 'từ chối'} {ticket_id}",
            ticket.title,
        )
        # Tin của chính người duyệt trong phòng chung. Không đi qua PolicyGate vì
        # cổng đó quản agent, không quản con người; quyết định đã nằm trong audit.
        self.room.append(
            RoomMessage(
                seq=len(self.room) + 1,
                at=self.clock.now,
                author=actor_name,
                mentions=(AGENT_NAMES[ticket.actions[0].proposed_by],),
                text=f"{'Duyệt' if approved else 'Từ chối'} {ticket_id}: {ticket.title}."
                + (f" {note}" if note else ""),
            )
        )
        if approved:
            for action in ticket.actions:
                self._run(workflow, action.proposed_by, action, ticket=ticket)

        if ticket.kind == TicketKind.INTERVENTION and not self._pending_of(workflow, TicketKind.INTERVENTION):
            self._after_interventions(workflow)
        elif ticket.kind == TicketKind.RESERVATION_CHANGE:
            self._finish_reservation(workflow, ticket)
        return ticket

    def _pending_of(self, workflow: CrowdWorkflow, kind: TicketKind) -> tuple[ApprovalTicket, ...]:
        return tuple(
            ticket
            for ticket in self.approvals.all()
            if ticket.workflow_id == workflow.workflow_id
            and ticket.kind == kind
            and ticket.status == TicketStatus.PENDING
        )

    # ---- giai đoạn 6: hậu phê duyệt — lịch trình rồi lịch đặt -----------------

    def _after_interventions(self, workflow: CrowdWorkflow) -> None:
        """14:12 — A3 → A1: chỉ gửi phần thay đổi cho từng khách đã được cấp fast-pass."""

        self.clock.advance(2)
        self._handoff(workflow, AgentId.OPS_DISPATCHER, "cập nhật lịch trình sau khi phương án được duyệt")
        granted = [
            ticket
            for ticket in self.approvals.all()
            if ticket.workflow_id == workflow.workflow_id
            and ticket.status == TicketStatus.APPROVED
            and any(action.action_type == ActionType.GRANT_FAST_PASS for action in ticket.actions)
        ]
        for ticket in granted:
            for action in ticket.actions:
                for guest_id in action.params.get("guest_ids", ()):
                    self._act(
                        workflow,
                        AgentId.GUEST_PLANNER,
                        ActionType.SEND_GUEST_MESSAGE,
                        f"Báo fast-pass cho {guest_id}",
                        {
                            "guest_id": str(guest_id),
                            "text": f"Mình đã xin được fast-pass {self.park.service(str(action.params['service_id'])).name} "
                            "cho anh/chị, phần còn lại của lịch giữ nguyên.",
                        },
                    )
        self._rescue_reservations(workflow)

    def _rescue_reservations(self, workflow: CrowdWorkflow) -> None:
        """14:14–14:17 — A1 → A4: cứu lịch đặt bị lệch, theo đúng thang xử lý."""

        self.clock.advance(2)
        self._handoff(workflow, AgentId.GUEST_PLANNER, "cứu lịch đặt bàn bị ảnh hưởng")
        touched = list(workflow.replanned_guest_ids) + list(workflow.unresolved_guest_ids)
        for guest_id in touched:
            for conflict in reservation_keeper.conflicts_for(self.park, guest_id, now=self.clock.now):
                reorder = guest_planner.reorder_around(
                    self.park,
                    guest_id,
                    protect_start=conflict.clash_start,
                    protect_end=self.park.reservation(conflict.reservation_id).at + timedelta(minutes=60),
                    now=self.clock.now,
                )
                plan = reservation_keeper.plan_rescue(self.park, conflict, reorder_patch=reorder, now=self.clock.now)
                self._run_rescue(workflow, plan, conflict.reservation_id)
        if not self._pending_of(workflow, TicketKind.RESERVATION_CHANGE):
            self._close(workflow)

    def _run_rescue(self, workflow: CrowdWorkflow, plan: reservation_keeper.RescuePlan, reservation_id: str) -> None:
        reservation = self.park.reservation(reservation_id)
        step_name = reservation_keeper.RESCUE_STEP_NAMES[plan.step]
        self._step(
            workflow,
            AgentId.RESERVATION_KEEPER.value,
            "rescue",
            f"{reservation.outlet_name} · {step_name}",
            plan.reason,
        )
        if plan.step == reservation_keeper.RescueStep.REORDER and plan.reorder_patch is not None:
            self._write_itinerary(workflow, plan.guest_id, plan.reorder_patch)
            workflow.rescued_reservation_ids.append(reservation_id)
            self.metrics.reservations_rescued += 1
            self._act(
                workflow,
                AgentId.RESERVATION_KEEPER,
                ActionType.SEND_GUEST_MESSAGE,
                f"Báo kết quả cứu lịch cho {plan.guest_id}",
                {"guest_id": plan.guest_id, "text": reservation_keeper.guest_notice(reservation, plan)},
            )
            return

        if plan.step == reservation_keeper.RescueStep.RESCHEDULE and plan.new_time is not None:
            action = self._new_action(
                workflow,
                AgentId.RESERVATION_KEEPER,
                ActionType.RESCHEDULE_RESERVATION,
                f"Dời bàn {reservation.outlet_name} sang {hhmm(plan.new_time)}",
                {
                    "reservation_id": reservation_id,
                    "guest_id": plan.guest_id,
                    "new_time": plan.new_time,
                    "channel": plan.channel.value if plan.channel else None,
                    "tried_reorder": plan.tried_reorder,
                    "tried_reschedule": plan.tried_reschedule,
                },
                affected_guests=reservation.party_size,
            )
            self._pending_conflicts[action.action_id] = (reservation_id, plan.guest_id, reservation.at)
            self._file_for_approval(
                workflow,
                action,
                kind=TicketKind.RESERVATION_CHANGE,
                title=f"Dời bàn {reservation.outlet_name} cho {plan.guest_id}",
                preview=reservation_keeper.guest_notice(reservation, plan),
            )
            return

        action = self._new_action(
            workflow,
            AgentId.RESERVATION_KEEPER,
            ActionType.CANCEL_RESERVATION,
            f"Huỷ bàn {reservation.outlet_name}",
            {
                "reservation_id": reservation_id,
                "guest_id": plan.guest_id,
                "tried_reorder": plan.tried_reorder,
                "tried_reschedule": plan.tried_reschedule,
            },
            affected_guests=reservation.party_size,
        )
        self._pending_conflicts[action.action_id] = (reservation_id, plan.guest_id, reservation.at)
        self._file_for_approval(
            workflow,
            action,
            kind=TicketKind.RESERVATION_CHANGE,
            title=f"Huỷ bàn {reservation.outlet_name} cho {plan.guest_id}",
            preview=reservation_keeper.guest_notice(reservation, plan),
        )

    def _finish_reservation(self, workflow: CrowdWorkflow, ticket: ApprovalTicket) -> None:
        """Khách đã duyệt: gọi đối tác xác nhận rồi báo lại kèm bằng chứng."""

        for action in ticket.actions:
            reservation_id, guest_id, old_time = self._pending_conflicts.pop(
                action.action_id, ("", "", self.clock.now)
            )
            if not reservation_id or ticket.status != TicketStatus.APPROVED:
                continue
            reservation = self.park.reservation(reservation_id)
            if action.action_type == ActionType.RESCHEDULE_RESERVATION:
                # Giờ mới đã ghi vào lịch đặt; kịch bản gọi cần đúng giờ cũ để đọc.
                call = self._new_action(
                    workflow,
                    AgentId.RESERVATION_KEEPER,
                    ActionType.CALL_PARTNER,
                    f"Gọi {reservation.outlet_name} xác nhận giờ mới",
                    reservation_keeper.call_params(
                        reservation.model_copy(update={"at": old_time}), reservation.at
                    ),
                )
                self._run(workflow, AgentId.RESERVATION_KEEPER, call)
            workflow.rescued_reservation_ids.append(reservation_id)
            self.metrics.reservations_rescued += 1
            self._act(
                workflow,
                AgentId.RESERVATION_KEEPER,
                ActionType.SEND_GUEST_MESSAGE,
                f"Báo kết quả cho {guest_id}",
                {
                    "guest_id": guest_id,
                    "text": ticket.guest_message_preview or "Lịch đặt của anh/chị đã được xử lý.",
                },
            )
        if not self._pending_of(workflow, TicketKind.RESERVATION_CHANGE):
            self._close(workflow)

    # ---- giai đoạn 7: đo lại, A2 xác nhận, đóng vòng --------------------------

    def _close(self, workflow: CrowdWorkflow) -> ImpactMeasurement:
        """14:30 — A3 → A2: đo lại, xác nhận điểm nghẽn đã giảm, khép vòng."""

        self.clock.advance(MEASURE_AFTER_MINUTES)
        self._handoff(workflow, AgentId.OPS_DISPATCHER, "xác nhận mật độ sau can thiệp")
        measurement = ops_dispatcher.measure(
            self.park,
            alert=workflow.alert,
            load_pct_before=workflow.alert.load_pct,
            guests_rerouted=len(workflow.replanned_guest_ids),
            now=self.clock.now,
        )
        self._act(
            workflow,
            AgentId.OPS_DISPATCHER,
            ActionType.MEASURE_IMPACT,
            f"Đo lại tải {workflow.alert.zone_name}",
            {"alert_id": workflow.alert.alert_id, "load_pct_after": measurement.load_pct_after},
        )
        confirmed = crowd_analyst.confirm(measurement)
        workflow.measurement = confirmed
        workflow.status = WorkflowStatus.CLOSED
        workflow.closed_at = self.clock.now
        workflow.waiting_for = []
        verdict = "đã giảm" if confirmed.confirmed_by_analyst else "chưa giảm"
        self._act(
            workflow,
            AgentId.CROWD_ANALYST,
            ActionType.POST_ROOM_MESSAGE,
            "Xác nhận sau can thiệp",
            {
                "text": f"{workflow.alert.zone_name}: {confirmed.load_pct_before:.0f}% → "
                f"{confirmed.load_pct_after:.0f}% ({confirmed.delta_pct:+.1f}). Điểm nghẽn {verdict}.",
                "mentions": [HUMAN_ROLE_NAMES[HumanRole.SHIFT_LEAD]],
            },
        )
        self._step(
            workflow,
            AgentId.CROWD_ANALYST.value,
            "closed",
            "Vòng việc khép lại",
            f"Không ai trong đội vận hành phải đứng ra điều phối bằng tay. Tải {verdict}.",
        )
        self._audit(
            workflow,
            AgentId.CROWD_ANALYST.value,
            "workflow.closed",
            f"{workflow.alert.zone_name} {verdict}",
            load_before=confirmed.load_pct_before,
            load_after=confirmed.load_pct_after,
            replanned=len(workflow.replanned_guest_ids),
            unresolved=len(workflow.unresolved_guest_ids),
            reservations_rescued=len(workflow.rescued_reservation_ids),
        )
        return confirmed

    # ---- hạ tầng dùng chung --------------------------------------------------

    def workflow(self, workflow_id: str) -> CrowdWorkflow:
        try:
            return self.workflows[workflow_id]
        except KeyError as exc:
            raise WorkflowNotFoundError(f"Không có workflow {workflow_id}") from exc

    def _new_action(
        self,
        workflow: CrowdWorkflow,
        agent: AgentId,
        action_type: ActionType,
        summary: str,
        params: dict[str, Any] | None = None,
        *,
        affected_guests: int = 0,
        cost_vnd: int = 0,
    ) -> ProposedAction:
        self._action_seq += 1
        action = ProposedAction(
            action_id=f"ACT-{self._action_seq:04d}",
            workflow_id=workflow.workflow_id,
            proposed_by=agent,
            action_type=action_type,
            summary=summary,
            params=params or {},
            affected_guests=affected_guests,
            estimated_cost_vnd=cost_vnd,
        )
        self._audit(
            workflow,
            agent.value,
            "action.proposed",
            summary,
            action_id=action.action_id,
            action_type=action_type.value,
            affected_guests=affected_guests,
        )
        return action

    def _act(
        self,
        workflow: CrowdWorkflow,
        agent: AgentId,
        action_type: ActionType,
        summary: str,
        params: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        action = self._new_action(workflow, agent, action_type, summary, params)
        return self._run(workflow, agent, action)

    def _run(
        self,
        workflow: CrowdWorkflow,
        agent: AgentId,
        action: ProposedAction,
        *,
        ticket: ApprovalTicket | None = None,
    ) -> GovernanceDecision:
        decision = self._call_tool(workflow, agent, action.summary, lambda: self.execute(action, ticket=ticket))
        gate = (
            f"policy gate: {decision.verdict.value} · {', '.join(decision.policy_codes)}"
            if ticket is None
            else f"thực hiện theo {ticket.ticket_id} đã duyệt"
        )
        self._step(workflow, agent.value, "action", action.summary, gate)
        return decision

    def _call_tool(self, workflow: CrowdWorkflow, agent: AgentId, label: str, call: Callable[[], T]) -> T:
        for attempt in range(1, TOOL_MAX_ATTEMPTS + 1):
            try:
                return call()
            except ToolUnavailableError as exc:
                self._audit(workflow, agent.value, "tool.failed", f"{label}: {exc}", attempt=attempt)
                if attempt == TOOL_MAX_ATTEMPTS:
                    raise
                self.metrics.tool_retries += 1
                self._step(workflow, agent.value, "retry", f"Thử lại: {label}", f"Lần {attempt} lỗi: {exc}")
        raise AssertionError("unreachable")

    def _handoff(self, workflow: CrowdWorkflow, source: AgentId, purpose: str) -> crew_pm.Routing:
        """Bàn giao đi qua A0: chọn đúng agent (và instance) theo bảng năng lực."""

        routing = crew_pm.handoff_target(purpose)
        self.metrics.handoffs += 1
        self._step(
            workflow,
            AgentId.CREW_PM.value,
            "handoff",
            f"{source.value} → {routing.agent.value} ({routing.instance_id})",
            f"{purpose}. {routing.reason}",
        )
        self._audit(
            workflow,
            AgentId.CREW_PM.value,
            "handoff",
            purpose,
            source=source.value,
            target=routing.agent.value,
            instance=routing.instance_id,
        )
        return routing

    def _step(self, workflow: CrowdWorkflow, actor: str, kind: str, title: str, detail: str = "") -> None:
        workflow.steps.append(
            WorkflowStep(
                seq=len(workflow.steps) + 1, at=self.clock.now, actor=actor, kind=kind, title=title, detail=detail
            )
        )

    def _audit(
        self, workflow: CrowdWorkflow | None, actor: str, event: str, detail: str, **data: Any
    ) -> None:
        self.audit.record(
            at=self.clock.now,
            actor=actor,
            event=event,
            detail=detail,
            workflow_id=workflow.workflow_id if workflow else None,
            **data,
        )

    # ---- báo cáo -------------------------------------------------------------

    def kpis(self) -> dict[str, Any]:
        return {
            "handoffs": self.metrics.handoffs,
            "auto_executed": self.metrics.auto_executed,
            "executed_with_approval": self.metrics.executed_with_approval,
            "blocked_actions": self.metrics.blocked_actions,
            "bypass_attempts_blocked": self.metrics.bypass_attempts_blocked,
            "tool_retries": self.metrics.tool_retries,
            "guests_replanned": self.metrics.guests_replanned,
            "guests_unresolved": self.metrics.guests_unresolved,
            "reservations_rescued": self.metrics.reservations_rescued,
            "audit_entries": len(self.audit.entries()),
            "audit_chain_valid": self.audit.verify(),
        }

    def snapshot(self, *, audit_limit: int = 120) -> dict[str, Any]:
        """Toàn bộ trạng thái dashboard cần, đọc một lần cho mỗi lần vẽ lại."""

        now = self.clock.now
        latest = next(reversed(self.workflows.values()), None) if self.workflows else None
        return {
            "clock": now.isoformat(),
            "zones": [zone.model_dump(mode="json") for zone in crowd_analyst.zone_picture(self.park)],
            "alerts": [alert.model_dump(mode="json") for alert in crowd_analyst.detect_alerts(self.park, now=now)],
            "workflows": [workflow.model_dump(mode="json") for workflow in reversed(self.workflows.values())],
            "trace": [step.model_dump(mode="json") for step in (latest.steps if latest else ())],
            "approvals": [ticket.model_dump(mode="json") for ticket in reversed(self.approvals.all())],
            "room": [message.model_dump(mode="json") for message in self.room],
            "messages": [message.model_dump(mode="json") for message in reversed(self.park.outbox)],
            "calls": [call.model_dump(mode="json") for call in reversed(self.park.calls)],
            "reservations": [
                reservation.model_dump(mode="json") for reservation in self.park.reservations.values()
            ],
            "audit": [entry.model_dump(mode="json") for entry in reversed(self.audit.entries()[-audit_limit:])],
            "kpis": self.kpis(),
            "park": {
                "fast_passes_issued": self.park.fast_passes_issued,
                "fast_pass_cap": FAST_PASS_SHIFT_CAP,
                "promotions": [promotion.model_dump(mode="json") for promotion in self.park.promotions],
                "extra_lanes": [
                    service.name for service in self.park.services.values() if service.extra_lane_open
                ],
                "closed_services": [
                    service.name
                    for service in self.park.services.values()
                    if service.status is ServiceStatus.CLOSED
                ],
            },
            "labels": {
                "agents": {agent.value: name for agent, name in AGENT_NAMES.items()},
                "roles": {role.value: name for role, name in HUMAN_ROLE_NAMES.items()},
            },
            "policies": POLICIES,
        }
