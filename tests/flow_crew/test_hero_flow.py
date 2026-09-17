"""Hero flow mục 7, chạy thật từ 14:05 tới khi A2 xác nhận.

Mỗi test dưới đây gắn với một US trong danh sách charter tuyên bố đã chứng minh
qua đúng một luồng: US-2 phòng chung · US-3 handoff · US-4 tự chạy đa bước ·
US-5 live trace · US-6 gọi tool · US-7 cổng phê duyệt · US-8 audit ·
US-9 least-privilege · US-12 cả 5 agent đều tham gia.
"""

from __future__ import annotations

import pytest

from src.flow_crew.contracts import (
    AGENT_NAMES,
    AgentId,
    HumanRole,
    TicketKind,
    TicketStatus,
    WorkflowStatus,
)
from src.flow_crew.engine import FlowCrewEngine
from src.flow_crew.mock_park import ToolUnavailableError


def _approve_everything(engine: FlowCrewEngine) -> None:
    for ticket in engine.approvals.pending():
        engine.decide(
            ticket.ticket_id,
            role=ticket.required_role,
            actor_name=f"người duyệt {ticket.required_role.value}",
            approved=True,
        )
    for ticket in engine.approvals.pending():  # ticket của khách mở ra sau khi can thiệp được duyệt
        engine.decide(
            ticket.ticket_id, role=HumanRole.GUEST, actor_name="khách hàng", approved=True
        )


@pytest.fixture
def finished(engine: FlowCrewEngine) -> FlowCrewEngine:
    engine.open_incident()
    _approve_everything(engine)
    return engine


# ---- giai đoạn 1-2 ----------------------------------------------------------


def test_the_goal_comes_from_a2_not_from_a_person_typing(engine: FlowCrewEngine) -> None:
    workflow = engine.open_incident()
    first = workflow.steps[0]
    assert first.kind == "goal"
    assert first.actor == AgentId.CROWD_ANALYST.value
    assert engine.room[0].author == AGENT_NAMES[AgentId.CROWD_ANALYST]


def test_forty_guests_split_into_twenty_eight_and_twelve(engine: FlowCrewEngine) -> None:
    workflow = engine.open_incident()
    assert workflow.alert.guests_heading == 40
    assert len(workflow.replanned_guest_ids) == 28
    assert len(workflow.unresolved_guest_ids) == 12


def test_each_replanned_guest_holds_a_real_seat(engine: FlowCrewEngine) -> None:
    """Xếp tuần tự nên không ai được phát trùng suất của ai."""

    workflow = engine.open_incident()
    seats = {}
    for guest_id in workflow.replanned_guest_ids:
        slot = next(
            slot for slot in engine.park.itinerary(guest_id).slots if slot.service_id in {"SW-AQUA", "SW-SEALION"}
        )
        seats[slot.service_id] = seats.get(slot.service_id, 0) + 1
    assert seats == {"SW-AQUA": 18, "SW-SEALION": 10}
    for service_id, taken in seats.items():
        service = engine.park.service(service_id)
        assert max(service.booked.values()) <= service.slot_capacity
        assert taken <= service.slot_capacity


# ---- US-3 handoff · US-12 cả đội ---------------------------------------------


def test_every_handoff_is_routed_by_a0(finished: FlowCrewEngine) -> None:
    handoffs = [step for step in _steps(finished) if step.kind == "handoff"]
    assert handoffs
    assert {step.actor for step in handoffs} == {AgentId.CREW_PM.value}
    assert finished.metrics.handoffs == len(handoffs)


def test_all_five_agents_take_part_in_the_flow(finished: FlowCrewEngine) -> None:
    actors = {step.actor for step in _steps(finished)}
    assert {agent.value for agent in AgentId} <= actors


# ---- US-7 cổng phê duyệt -----------------------------------------------------


def test_three_packages_wait_for_three_different_desks(engine: FlowCrewEngine) -> None:
    engine.open_incident()
    pending = engine.approvals.pending()
    assert len(pending) == 3
    assert {ticket.required_role for ticket in pending} == {
        HumanRole.SHIFT_LEAD,
        HumanRole.MARKETING,
        HumanRole.PARK_MANAGER,
    }
    assert all(ticket.kind == TicketKind.INTERVENTION for ticket in pending)


def test_nothing_touches_the_park_before_a_signature(engine: FlowCrewEngine) -> None:
    engine.open_incident()
    assert engine.approvals.pending()
    assert engine.park.fast_passes_issued == 0
    assert engine.park.promotions == []
    assert all(not service.extra_lane_open for service in engine.park.services.values())
    assert engine.metrics.executed_with_approval == 0


def test_a_rejected_package_never_runs(engine: FlowCrewEngine) -> None:
    engine.open_incident()
    ticket = next(t for t in engine.approvals.pending() if t.required_role == HumanRole.PARK_MANAGER)
    engine.decide(ticket.ticket_id, role=HumanRole.PARK_MANAGER, actor_name="QLCV", approved=False)
    assert engine.approvals.get(ticket.ticket_id).status == TicketStatus.REJECTED
    assert engine.park.fast_passes_issued == 0


def test_the_guest_signs_their_own_reservation_change(finished: FlowCrewEngine) -> None:
    guest_tickets = [
        ticket for ticket in finished.approvals.all() if ticket.kind == TicketKind.RESERVATION_CHANGE
    ]
    assert guest_tickets
    for ticket in guest_tickets:
        assert ticket.required_role == HumanRole.GUEST
        assert ticket.decided_role == HumanRole.GUEST


# ---- A4 · kết quả cứu lịch đặt ----------------------------------------------


def test_two_tables_are_saved_by_reordering_and_one_by_moving_the_booking(
    finished: FlowCrewEngine,
) -> None:
    workflow = next(iter(finished.workflows.values()))
    assert len(workflow.rescued_reservation_ids) == 3

    moved = [item for item in finished.park.reservations.values() if item.status.value == "rescheduled"]
    assert len(moved) == 1
    assert not [item for item in finished.park.reservations.values() if item.status.value == "cancelled"]


def test_the_partner_call_leaves_evidence(finished: FlowCrewEngine) -> None:
    assert finished.park.calls
    call = finished.park.calls[0]
    assert call.duration_seconds <= 120
    assert "trợ lý tự động" in call.transcript[0]
    moved = next(item for item in finished.park.reservations.values() if item.status.value == "rescheduled")
    assert moved.evidence


def test_every_affected_guest_hears_back(finished: FlowCrewEngine) -> None:
    workflow = next(iter(finished.workflows.values()))
    told = {message.guest_id for message in finished.park.outbox}
    assert set(workflow.replanned_guest_ids) <= told
    assert set(workflow.unresolved_guest_ids) <= told


# ---- US-8 audit + đóng vòng --------------------------------------------------


def test_the_loop_closes_with_a2_confirming_the_drop(finished: FlowCrewEngine) -> None:
    workflow = next(iter(finished.workflows.values()))
    assert workflow.status == WorkflowStatus.CLOSED
    assert workflow.measurement is not None
    assert workflow.measurement.delta_pct < 0
    assert workflow.measurement.confirmed_by_analyst is True
    assert workflow.waiting_for == []


def test_the_audit_chain_covers_the_flow_and_verifies(finished: FlowCrewEngine) -> None:
    entries = finished.audit.entries()
    events = {entry.event for entry in entries}
    assert {
        "alert.raised",
        "handoff",
        "action.proposed",
        "governance.decision",
        "approval.requested",
        "approval.decided",
        "action.executed",
        "workflow.closed",
    } <= events
    assert finished.audit.verify() is True


def test_a_tampered_audit_entry_breaks_the_chain(finished: FlowCrewEngine) -> None:
    entries = list(finished.audit.entries())
    victim = entries[len(entries) // 2]
    object.__setattr__(victim, "detail", "đã sửa lại lịch sử")
    assert finished.audit.verify() is False


def test_every_executed_action_names_the_policy_that_allowed_it(finished: FlowCrewEngine) -> None:
    executed = [entry for entry in finished.audit.entries() if entry.event == "action.executed"]
    assert executed
    assert all(entry.data.get("policy_codes") for entry in executed)


# ---- US-6 gọi tool: hỏng thì thử lại -----------------------------------------


def test_a_flaky_park_system_is_retried_not_dropped(engine: FlowCrewEngine) -> None:
    engine.park.inject_failure("app", times=1)
    workflow = engine.open_incident()
    assert engine.metrics.tool_retries == 1
    assert any(step.kind == "retry" for step in workflow.steps)
    assert len(workflow.replanned_guest_ids) == 28


def test_a_system_that_stays_down_surfaces_instead_of_failing_silently(engine: FlowCrewEngine) -> None:
    engine.park.inject_failure("app", times=5)
    with pytest.raises(ToolUnavailableError):
        engine.open_incident()


# ---- tổng kết ---------------------------------------------------------------


def test_kpis_report_the_shape_of_the_run(finished: FlowCrewEngine) -> None:
    kpis = finished.kpis()
    assert kpis["guests_replanned"] == 28
    assert kpis["guests_unresolved"] == 12
    assert kpis["reservations_rescued"] == 3
    assert kpis["executed_with_approval"] == 4
    assert kpis["bypass_attempts_blocked"] == 0
    assert kpis["audit_chain_valid"] is True


def _steps(engine: FlowCrewEngine):
    return [step for workflow in engine.workflows.values() for step in workflow.steps]
