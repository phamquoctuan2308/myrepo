"""Mỗi giới hạn ở mục 6 của charter là một test ở đây.

Một guardrail chỉ đáng tin khi nó hỏng thì có test đỏ. Các test dưới đây cố ý
làm đúng những việc charter cấm, và khẳng định hệ thống chặn — chứ không phải
khẳng định prompt có nhắc tới điều cấm đó.
"""

from __future__ import annotations

import pytest

from src.flow_crew.agents import reservation_keeper
from src.flow_crew.clock import at
from src.flow_crew.contracts import (
    ActionType,
    AgentId,
    ChangeKind,
    HumanRole,
    ItineraryChange,
    ItineraryPatch,
    ProposedAction,
    Verdict,
    can_approve,
)
from src.flow_crew.engine import ApprovalBypassError, FlowCrewEngine
from src.flow_crew.governance import PolicyGate
from src.flow_crew.mock_park import FAST_PASS_SHIFT_CAP, MockPark


def _action(
    agent: AgentId,
    action_type: ActionType,
    params: dict | None = None,
    *,
    affected_guests: int = 5,
) -> ProposedAction:
    return ProposedAction(
        action_id="ACT-TEST",
        workflow_id="WF-TEST",
        proposed_by=agent,
        action_type=action_type,
        summary="hành động thử",
        params=params or {},
        affected_guests=affected_guests,
    )


def _verdict(park: MockPark, action: ProposedAction):
    return PolicyGate(park).evaluate(action)


# ---- least privilege ---------------------------------------------------------


@pytest.mark.parametrize(
    "action_type",
    [ActionType.OPEN_EXTRA_LANE, ActionType.GRANT_FAST_PASS, ActionType.UPDATE_ITINERARY],
)
def test_analyst_has_no_write_power_at_all(park: MockPark, action_type: ActionType) -> None:
    decision = _verdict(park, _action(AgentId.CROWD_ANALYST, action_type, {"service_id": "SW-AQUA"}))
    assert decision.verdict == Verdict.BLOCK
    assert "POL-PRIV-01" in decision.policy_codes


def test_crew_pm_may_report_but_never_execute(park: MockPark) -> None:
    posting = _verdict(park, _action(AgentId.CREW_PM, ActionType.POST_ROOM_MESSAGE, {"text": "báo cáo"}))
    assert posting.verdict == Verdict.PASS

    ordering = _verdict(park, _action(AgentId.CREW_PM, ActionType.OPEN_EXTRA_LANE, {"service_id": "SW-AQUA"}))
    assert ordering.verdict == Verdict.BLOCK
    assert "POL-PRIV-02" in ordering.policy_codes


def test_agent_cannot_take_over_another_agents_job(park: MockPark) -> None:
    """A1 không được tự cấp fast-pass, dù đó là việc có thật trong hero flow."""

    decision = _verdict(park, _action(AgentId.GUEST_PLANNER, ActionType.GRANT_FAST_PASS, {"service_id": "SW-AQUA"}))
    assert decision.verdict == Verdict.BLOCK


# ---- A1 · lịch trình ---------------------------------------------------------


def test_planner_cannot_write_another_guests_itinerary(park: MockPark) -> None:
    decision = _verdict(
        park,
        _action(
            AgentId.GUEST_PLANNER,
            ActionType.UPDATE_ITINERARY,
            {"guest_id": "G-002", "speaking_with": "G-001"},
        ),
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-PRIV-03" in decision.policy_codes


def test_planner_cannot_move_a_slot_the_guest_locked(park: MockPark) -> None:
    decision = _verdict(
        park,
        _action(
            AgentId.GUEST_PLANNER,
            ActionType.UPDATE_ITINERARY,
            {"guest_id": "G-014", "speaking_with": "G-014", "touches_locked_slot": True},
        ),
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-GUEST-03" in decision.policy_codes


def test_locked_slot_flag_comes_from_the_itinerary_not_the_agent(park: MockPark) -> None:
    """Cờ `touches_locked_slot` được tính từ dữ liệu, nên agent không khai gian được."""

    from src.flow_crew.agents import guest_planner

    itinerary = park.itinerary("G-014")
    booked = next(slot for slot in itinerary.slots if slot.locked)
    patch = ItineraryPatch(
        guest_id="G-014",
        changes=(
            ItineraryChange(
                kind=ChangeKind.MOVED,
                from_service_id=booked.service_id,
                from_service_name=booked.service_name,
                to_service_id=booked.service_id,
                to_service_name=booked.service_name,
                new_start=at(18, 0),
            ),
        ),
    )
    assert guest_planner.touches_locked_slot(itinerary, patch) is True


# ---- A3 · can thiệp ----------------------------------------------------------


def test_no_intervention_on_a_service_paused_for_safety(park: MockPark) -> None:
    decision = _verdict(
        park, _action(AgentId.OPS_DISPATCHER, ActionType.OPEN_EXTRA_LANE, {"service_id": "SW-SPLASH"})
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-OPS-04" in decision.policy_codes


def test_vague_proposal_is_refused(park: MockPark) -> None:
    decision = _verdict(
        park,
        _action(AgentId.OPS_DISPATCHER, ActionType.PUSH_PROMOTION, {"service_id": "FB-LAGOON"}, affected_guests=0),
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-SCOPE-01" in decision.policy_codes


def test_fast_pass_cannot_exceed_the_shift_cap(park: MockPark) -> None:
    decision = _verdict(
        park,
        _action(
            AgentId.OPS_DISPATCHER,
            ActionType.GRANT_FAST_PASS,
            {"service_id": "SW-AQUA", "guest_ids": []},
            affected_guests=FAST_PASS_SHIFT_CAP + 1,
        ),
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-TICKET-02" in decision.policy_codes


def test_fast_pass_only_where_the_service_supports_it(park: MockPark) -> None:
    decision = _verdict(
        park,
        _action(AgentId.OPS_DISPATCHER, ActionType.GRANT_FAST_PASS, {"service_id": "SW-SEALION", "guest_ids": []}),
    )
    assert decision.verdict == Verdict.REQUIRE_APPROVAL

    unsupported = _verdict(
        park,
        _action(AgentId.OPS_DISPATCHER, ActionType.GRANT_FAST_PASS, {"service_id": "FB-OCEAN", "guest_ids": []}),
    )
    assert unsupported.verdict == Verdict.BLOCK
    assert "POL-TICKET-03" in unsupported.policy_codes


# ---- A4 · lịch đặt & cuộc gọi ------------------------------------------------


def test_cancelling_before_trying_the_cheaper_rungs_is_refused(park: MockPark) -> None:
    decision = _verdict(
        park,
        _action(AgentId.RESERVATION_KEEPER, ActionType.CANCEL_RESERVATION, {"reservation_id": "RS-014"}),
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-RES-02" in decision.policy_codes


def test_a_reservation_is_never_cancelled_twice(park: MockPark) -> None:
    park.cancel_reservation("RS-014")
    decision = _verdict(
        park,
        _action(
            AgentId.RESERVATION_KEEPER,
            ActionType.CANCEL_RESERVATION,
            {"reservation_id": "RS-014", "tried_reorder": True, "tried_reschedule": True},
        ),
    )
    assert decision.verdict == Verdict.BLOCK
    assert "POL-RES-03" in decision.policy_codes


def test_call_must_disclose_bot_and_ask_for_recording_consent(park: MockPark) -> None:
    reservation = park.reservation("RS-014")
    params = reservation_keeper.call_params(reservation, at(16, 0))
    assert _verdict(park, _action(AgentId.RESERVATION_KEEPER, ActionType.CALL_PARTNER, params)).verdict == Verdict.PASS

    silent = dict(params) | {"discloses_bot": False}
    decision = _verdict(park, _action(AgentId.RESERVATION_KEEPER, ActionType.CALL_PARTNER, silent))
    assert decision.verdict == Verdict.BLOCK
    assert "POL-CALL-01" in decision.policy_codes


def test_call_never_reads_payment_details(park: MockPark) -> None:
    reservation = park.reservation("RS-014")
    params = dict(reservation_keeper.call_params(reservation, at(16, 0)))
    params["script"] = [*params["script"], "Số thẻ của khách là 4111 1111 1111 1111."]
    decision = _verdict(park, _action(AgentId.RESERVATION_KEEPER, ActionType.CALL_PARTNER, params))
    assert decision.verdict == Verdict.BLOCK
    assert "POL-CALL-02" in decision.policy_codes


def test_rescue_ladder_climbs_in_order() -> None:
    steps = list(reservation_keeper.RescueStep)
    assert steps.index(reservation_keeper.RescueStep.REORDER) < steps.index(
        reservation_keeper.RescueStep.RESCHEDULE
    ) < steps.index(reservation_keeper.RescueStep.CANCEL)


# ---- cổng phê duyệt ----------------------------------------------------------


def test_nobody_signs_on_behalf_of_a_guest() -> None:
    assert can_approve(HumanRole.GUEST, HumanRole.GUEST) is True
    assert can_approve(HumanRole.PARK_MANAGER, HumanRole.GUEST) is False
    assert can_approve(HumanRole.GUEST, HumanRole.SHIFT_LEAD) is False


def test_park_manager_spans_operational_roles() -> None:
    assert can_approve(HumanRole.PARK_MANAGER, HumanRole.SHIFT_LEAD) is True
    assert can_approve(HumanRole.PARK_MANAGER, HumanRole.MARKETING) is True
    assert can_approve(HumanRole.SHIFT_LEAD, HumanRole.MARKETING) is False


def test_an_approved_action_cannot_be_executed_without_its_ticket(engine: FlowCrewEngine) -> None:
    engine.open_incident()
    ticket = engine.approvals.pending()[0]
    with pytest.raises(ApprovalBypassError):
        engine.execute(ticket.actions[0])
    assert engine.metrics.bypass_attempts_blocked == 1


def test_a_signature_from_the_wrong_desk_does_not_unlock_the_action(engine: FlowCrewEngine) -> None:
    """Chữ ký của Trưởng ca không làm chạy được gói cần Marketing duyệt."""

    engine.open_incident()
    marketing_ticket = next(
        ticket for ticket in engine.approvals.pending() if ticket.required_role == HumanRole.MARKETING
    )
    with pytest.raises(PermissionError):
        engine.decide(
            marketing_ticket.ticket_id,
            role=HumanRole.SHIFT_LEAD,
            actor_name="Trưởng ca",
            approved=True,
        )
    assert engine.park.promotions == []
