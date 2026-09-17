"""Chạy hero flow mục 7 và in ra đúng thứ mà buổi demo cần thấy.

    .venv/Scripts/python.exe -m src.flow_crew.demo

Không cần database, không cần API key: mọi thứ chạy trên `MockPark` với seed cố
định, nên hai lần chạy cho ra cùng một dòng thời gian.
"""

from __future__ import annotations

from src.flow_crew.clock import SimClock, at, hhmm
from src.flow_crew.contracts import HUMAN_ROLE_NAMES, AgentId, HumanRole, TicketStatus
from src.flow_crew.engine import FlowCrewEngine

APPROVERS: dict[HumanRole, str] = {
    HumanRole.SHIFT_LEAD: "Trưởng ca Nguyễn Văn An",
    HumanRole.MARKETING: "Marketing Lê Thu Hà",
    HumanRole.PARK_MANAGER: "Quản lý công viên Trần Bá Minh",
    HumanRole.GUEST: "Khách hàng",
}


def _rule(title: str) -> None:
    print(f"\n{'─' * 78}\n{title}\n{'─' * 78}")


def run(*, verbose: bool = True) -> FlowCrewEngine:
    engine = FlowCrewEngine(clock=SimClock(at(14, 5)))

    if verbose:
        _rule("US-1 · mỗi agent trả lời được ngay khi bị hỏi thẳng")
        for agent, question in (
            (AgentId.CREW_PM, "Kiểm tra tình hình khu Sea World giúp tôi"),
            (AgentId.CROWD_ANALYST, "Mật độ Fairy Land hiện giờ thế nào?"),
            (AgentId.GUEST_PLANNER, "Cho tôi lịch trình chơi 1 ngày"),
            (AgentId.OPS_DISPATCHER, "Khu nào đang cần can thiệp?"),
            (AgentId.RESERVATION_KEEPER, "Đổi giờ đặt bàn giúp tôi"),
        ):
            answer = engine.ask(agent, question, guest_id="G-014")
            print(f"\n[{agent.value}] {question}")
            for line in answer.text.splitlines():
                print(f"    {line}")

    _rule("Hero flow · 14:05 một dịch vụ Sea World đóng đột xuất")
    workflow = engine.open_incident()

    pending = engine.approvals.pending()
    print(f"\n{len(pending)} gói can thiệp đang chờ duyệt song song:")
    for ticket in pending:
        print(f"  {ticket.ticket_id} · {ticket.title} → {HUMAN_ROLE_NAMES[ticket.required_role]}")

    for ticket in pending:
        engine.decide(
            ticket.ticket_id,
            role=ticket.required_role,
            actor_name=APPROVERS[ticket.required_role],
            approved=True,
            note="Duyệt trong ca",
        )

    for ticket in engine.approvals.pending():
        engine.decide(
            ticket.ticket_id,
            role=HumanRole.GUEST,
            actor_name=APPROVERS[HumanRole.GUEST],
            approved=True,
            note="Khách đồng ý dời giờ ăn",
        )

    _rule("Phòng chung (US-2)")
    for message in engine.room:
        mentions = f" → {', '.join(message.mentions)}" if message.mentions else ""
        print(f"{hhmm(message.at)} {message.author}{mentions}\n    {message.text}")

    _rule("Live trace (US-4 · US-5)")
    for step in workflow.steps:
        detail = f" — {step.detail}" if step.detail else ""
        print(f"{hhmm(step.at)} [{step.kind:<16}] {step.actor:<12} {step.title}{detail}")

    _rule("Kết quả")
    print(f"Trạng thái workflow      : {workflow.status.value}")
    print(f"Khách được xếp lại lịch  : {len(workflow.replanned_guest_ids)}")
    print(f"Khách không còn phương án: {len(workflow.unresolved_guest_ids)}")
    print(f"Lịch đặt bàn được cứu    : {len(workflow.rescued_reservation_ids)}")
    if workflow.measurement is not None:
        measurement = workflow.measurement
        print(
            f"Tải {workflow.alert.zone_name}: {measurement.load_pct_before:.1f}% → "
            f"{measurement.load_pct_after:.1f}% ({measurement.delta_pct:+.1f}) · "
            f"A2 xác nhận: {'có' if measurement.confirmed_by_analyst else 'chưa'}"
        )

    _rule("Phê duyệt (US-7) & audit (US-8)")
    for ticket in engine.approvals.all():
        mark = "✓" if ticket.status == TicketStatus.APPROVED else "✗"
        print(
            f"{mark} {ticket.ticket_id} · {ticket.title} · {HUMAN_ROLE_NAMES[ticket.required_role]}"
            f" · {ticket.decided_by or 'chưa quyết'}"
        )
    for key, value in engine.kpis().items():
        print(f"{key:<26}: {value}")
    return engine


if __name__ == "__main__":  # pragma: no cover
    run()
