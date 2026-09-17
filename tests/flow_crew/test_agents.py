"""Từng vai làm đúng việc của mình, kể cả khi bị hỏi thẳng (US-1)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from src.flow_crew.agents import (
    crew_pm,
    crowd_analyst,
    guest_planner,
    ops_dispatcher,
    reservation_keeper,
)
from src.flow_crew.clock import at
from src.flow_crew.contracts import AgentId, DensityLevel, WaitSource
from src.flow_crew.engine import FlowCrewEngine
from src.flow_crew.mock_park import (
    TOTAL_SERVICE_POINTS,
    ZONE_ALERT_LOAD_PCT,
    ZONES,
    GuestParty,
    MockPark,
)


def test_park_matches_the_charter_numbers(park: MockPark) -> None:
    assert len(ZONES) == 6
    assert len(park.services) == TOTAL_SERVICE_POINTS


# ---- A2 · chỉ quan sát -------------------------------------------------------


def test_no_alerts_while_every_zone_is_under_the_threshold(park: MockPark) -> None:
    assert crowd_analyst.detect_alerts(park, now=at(14, 5)) == ()
    assert all(zone.load_pct < ZONE_ALERT_LOAD_PCT for zone in crowd_analyst.zone_picture(park))


def test_closing_a_service_raises_a_ranked_alert_with_a_cause(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alerts = crowd_analyst.detect_alerts(park, now=now)

    assert [alert.rank for alert in alerts] == list(range(1, len(alerts) + 1))
    assert [alert.severity_score for alert in alerts] == sorted(
        (alert.severity_score for alert in alerts), reverse=True
    )
    top = alerts[0]
    assert top.zone_id == "Z-SEA"
    assert top.cause.value == "service_closed"
    assert top.threshold_pct == ZONE_ALERT_LOAD_PCT
    assert top.guests_heading == 40
    assert top.level in {DensityLevel.CROWDED, DensityLevel.OVERLOAD}


def test_analyst_uses_the_configured_threshold_not_one_of_its_own(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    for alert in crowd_analyst.detect_alerts(park, now=now):
        assert alert.threshold_pct == ZONE_ALERT_LOAD_PCT


def test_analyst_reads_guest_plans_only_as_a_count(park: MockPark) -> None:
    """A2 biết bao nhiêu khách đang hướng tới điểm nghẽn, không biết họ là ai."""

    heading = park.guests_heading_to("SW-DOLPHIN", after=at(14, 5))
    assert isinstance(heading, int)
    source = Path(crowd_analyst.__file__).read_text(encoding="utf-8")
    assert "guest_ids_heading_to" not in source


def test_wait_estimate_says_how_it_was_measured(park: MockPark) -> None:
    measured = crowd_analyst.wait_for(park, "SW-AQUA", now=at(14, 5))
    assert measured.source == WaitSource.CAMERA
    assert "camera" in measured.phrasing

    guessed = crowd_analyst.wait_for(park, "WP-SLIDE", now=at(14, 5))
    assert guessed.source == WaitSource.ESTIMATE
    assert "ước lượng" in guessed.phrasing


def test_measurement_is_only_confirmed_when_load_actually_fell(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alert = crowd_analyst.detect_alerts(park, now=now)[0]
    worse = crowd_analyst.measure(
        park, alert=alert, load_pct_before=alert.load_pct - 20, guests_rerouted=0, now=now
    )
    assert crowd_analyst.confirm(worse).confirmed_by_analyst is False


# ---- A1 · lịch trình khách ---------------------------------------------------


def test_planner_never_suggests_a_ride_the_children_are_too_short_for(park: MockPark) -> None:
    family = GuestParty(adults=2, children=2, shortest_height_cm=105, youngest_age=6, thrill_ok=False)
    assert guest_planner.is_allowed(park, park.service("WP-SLIDE"), family, at(11, 0)) is False

    adults = GuestParty(adults=2, shortest_height_cm=170, youngest_age=30)
    assert guest_planner.is_allowed(park, park.service("WP-SLIDE"), adults, at(11, 0)) is True


def test_planner_keeps_outdoor_activities_out_of_the_rain_window(park: MockPark) -> None:
    party = GuestParty(adults=2)
    outdoor = park.service("FH-SKY")
    assert park.rains_at(at(16, 0)) is True
    assert guest_planner.is_allowed(park, outdoor, party, at(16, 0)) is False
    assert guest_planner.is_allowed(park, outdoor, party, at(13, 0)) is True


def test_planner_will_not_suggest_a_service_paused_for_safety(park: MockPark) -> None:
    assert guest_planner.is_allowed(park, park.service("SW-SPLASH"), GuestParty(adults=2), at(14, 30)) is False


def test_replan_changes_only_the_broken_slot(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alert = crowd_analyst.detect_alerts(park, now=now)[0]
    before = park.itinerary("G-001").model_copy(deep=True)

    patch = guest_planner.replan(park, "G-001", alert=alert, now=now)
    assert len(patch.changes) == 1
    assert patch.changes[0].from_service_id == "SW-DOLPHIN"

    after = guest_planner.apply_patch(before.model_copy(deep=True), patch, park)
    untouched = {slot.service_id for slot in before.slots} - {"SW-DOLPHIN"}
    assert untouched <= {slot.service_id for slot in after.slots}


def test_replan_stays_inside_the_guests_own_part_of_the_day(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alert = crowd_analyst.detect_alerts(park, now=now)[0]
    patch = guest_planner.replan(park, "G-001", alert=alert, now=now)
    new_start = patch.changes[0].new_start
    assert new_start is not None
    assert new_start <= at(14, 30) + timedelta(minutes=guest_planner.REPLAN_WINDOW_MINUTES)


def test_replan_refuses_rather_than_inventing_a_worse_option(park: MockPark) -> None:
    """Hết suất thì nói hết suất — không đẩy khách sang một trò nhỏ cho có."""

    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alert = crowd_analyst.detect_alerts(park, now=now)[0]
    resolved = 0
    unresolved = []
    for guest_id in park.guest_ids_heading_to("SW-DOLPHIN", after=now):
        patch = guest_planner.replan(park, guest_id, alert=alert, now=now)
        if patch.changes:
            change = patch.changes[0]
            assert change.new_start is not None and change.to_service_id is not None
            park.book_slot(change.to_service_id, change.new_start, 1)
            resolved += 1
        else:
            assert patch.resolved is False and patch.unresolved_reason
            unresolved.append(guest_id)
    assert (resolved, len(unresolved)) == (28, 12)


def test_planner_builds_a_day_when_simply_asked(park: MockPark) -> None:
    itinerary = guest_planner.build_itinerary(park, "G-050", now=at(10, 0))
    assert itinerary.slots
    starts = [slot.start for slot in itinerary.slots]
    assert starts == sorted(starts)
    assert len({slot.service_id for slot in itinerary.slots}) == len(itinerary.slots)


# ---- A3 · phương án ----------------------------------------------------------


def test_options_are_ordered_cheapest_first_and_never_vague(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alerts = crowd_analyst.detect_alerts(park, now=now)
    options = ops_dispatcher.build_package(
        park,
        alert=alerts[0],
        unresolved_guest_ids=tuple(f"G-{index:03d}" for index in range(29, 41)),
        congested_zone_ids=frozenset(alert.zone_id for alert in alerts),
    )
    assert len(options) == 3
    costs = [option.estimated_cost_vnd for option in options]
    assert costs == sorted(costs)
    assert all(option.affected_guests > 0 for option in options)
    assert {option.approver_role.value for option in options} == {"shift_lead", "marketing", "park_manager"}


def test_promotion_never_pushes_guests_into_another_congested_zone(park: MockPark) -> None:
    now = at(14, 5)
    park.close_service("SW-DOLPHIN", now)
    alerts = crowd_analyst.detect_alerts(park, now=now)
    congested = frozenset(alert.zone_id for alert in alerts)
    assert len(congested) > 1

    options = ops_dispatcher.build_package(park, alert=alerts[0], congested_zone_ids=congested)
    promotion = next(option for option in options if option.action_type.value == "push_promotion")
    outlet = park.service(str(promotion.params["service_id"]))
    assert outlet.zone_id == alerts[0].zone_id or outlet.zone_id not in congested


# ---- A4 · lịch đặt -----------------------------------------------------------


def test_reorder_is_tried_before_moving_the_table(park: MockPark) -> None:
    now = at(14, 5)
    reservation = park.reservation("RS-014")
    conflict = reservation_keeper.ConflictWindow(
        reservation_id="RS-014",
        guest_id="G-014",
        clash_service_id="SW-AQUA",
        clash_service_name="Đường hầm Thuỷ cung",
        clash_start=at(15, 0),
        clash_end=at(15, 40),
        shortfall_minutes=20,
    )
    workable = guest_planner.reorder_around(
        park, "G-014", protect_start=at(15, 0), protect_end=reservation.at + timedelta(minutes=60), now=now
    )
    plan = reservation_keeper.plan_rescue(park, conflict, reorder_patch=workable, now=now)
    assert plan.step == reservation_keeper.RescueStep.NOTHING_TO_DO or plan.tried_reorder


def test_channel_prefers_the_booking_system_over_the_phone(park: MockPark) -> None:
    assert reservation_keeper.preferred_channel(park, park.reservation("RS-014")).value == "booking_system"
    assert reservation_keeper.preferred_channel(park, park.reservation("RS-025")).value == "phone"


def test_call_script_opens_by_saying_it_is_a_bot(park: MockPark) -> None:
    script = reservation_keeper.call_script(park.reservation("RS-025"), at(16, 0))
    assert "trợ lý tự động" in script[0]
    assert "ghi âm" in script[1]
    assert park.reservation("RS-025").confirmation_code in " ".join(script)


# ---- A0 · điều phối ----------------------------------------------------------


def test_router_sends_each_question_to_the_owning_agent() -> None:
    assert crew_pm.route("Mật độ Fairy Land hiện giờ thế nào?").agent is AgentId.CROWD_ANALYST
    assert crew_pm.route("Cho tôi lịch trình chơi 1 ngày").agent is AgentId.GUEST_PLANNER
    assert crew_pm.route("Khu nào đang cần can thiệp?").agent is AgentId.OPS_DISPATCHER
    assert crew_pm.route("Đổi giờ đặt bàn giúp tôi").agent is AgentId.RESERVATION_KEEPER


def test_unknown_questions_fall_back_to_the_read_only_agent() -> None:
    routing = crew_pm.route("hôm nay trời đẹp nhỉ")
    assert routing.agent is AgentId.CROWD_ANALYST


def test_routing_names_an_instance_so_scaling_does_not_rewrite_callers() -> None:
    assert crew_pm.route("lịch trình").instance_id == "A10"


def test_report_lines_always_name_the_agent_that_said_them() -> None:
    summary = crew_pm.summarise(
        (
            crew_pm.ReportLine(agent=AgentId.CROWD_ANALYST, text="Sea World 89%."),
            crew_pm.ReportLine(agent=AgentId.OPS_DISPATCHER, text="3 phương án sẵn sàng."),
        )
    )
    assert summary.splitlines() == ["A2 · Crowd Analyst: Sea World 89%.", "A3 · Ops Dispatcher: 3 phương án sẵn sàng."]


# ---- US-1 · hỏi thẳng, không cần chuỗi sự cố ---------------------------------


def test_every_agent_answers_a_direct_question_with_no_incident_running(engine: FlowCrewEngine) -> None:
    questions = {
        AgentId.CREW_PM: "Kiểm tra tình hình khu Sea World giúp tôi",
        AgentId.CROWD_ANALYST: "Mật độ Fairy Land hiện giờ thế nào?",
        AgentId.GUEST_PLANNER: "Cho tôi lịch trình chơi 1 ngày",
        AgentId.OPS_DISPATCHER: "Khu nào đang cần can thiệp?",
        AgentId.RESERVATION_KEEPER: "Đổi giờ đặt bàn giúp tôi",
    }
    for agent, question in questions.items():
        answer = engine.ask(agent, question, guest_id="G-014")
        assert answer.agent is agent
        assert answer.text.strip()
    assert engine.workflows == {}
    assert engine.approvals.all() == ()
