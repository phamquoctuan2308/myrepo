"""Hộp duyệt: nơi duy nhất chữ ký của con người đi vào hệ thống.

Một ticket được quyết đúng một lần, bởi một vai có thẩm quyền trên đúng nhóm
việc của nó. Hành động đã bị BLOCK không bao giờ được đưa vào ticket — hỏi
người duyệt ký một thứ luật đã cấm chính là biến phê duyệt thành đường vòng.

Hero flow mục 7 mở ba ticket song song (Trưởng ca · Marketing · Quản lý công
viên): mỗi gói can thiệp chờ đúng người của nó, không gói nào chặn gói nào.
"""

from __future__ import annotations

from datetime import datetime

from src.flow_crew.contracts import (
    ApprovalTicket,
    GovernanceDecision,
    HumanRole,
    ProposedAction,
    TicketKind,
    TicketStatus,
    Verdict,
    can_approve,
)
from src.flow_crew.governance import required_role


class TicketNotFoundError(LookupError):
    pass


class TicketAlreadyDecidedError(RuntimeError):
    pass


class ApprovalPermissionError(PermissionError):
    pass


class ApprovalQueue:
    def __init__(self) -> None:
        self._tickets: dict[str, ApprovalTicket] = {}

    def open(
        self,
        *,
        workflow_id: str,
        kind: TicketKind,
        title: str,
        actions: tuple[ProposedAction, ...],
        decisions: tuple[GovernanceDecision, ...],
        at: datetime,
        urgent: bool = False,
        guest_message_preview: str | None = None,
    ) -> ApprovalTicket:
        if any(decision.verdict == Verdict.BLOCK for decision in decisions):
            raise ValueError("Hành động đã bị chặn thì không được đưa ra phê duyệt")
        if {decision.action_id for decision in decisions} != {action.action_id for action in actions}:
            raise ValueError("Mỗi hành động trong ticket cần đúng một phán quyết")
        ticket = ApprovalTicket(
            ticket_id=f"AP-{len(self._tickets) + 1:04d}",
            workflow_id=workflow_id,
            kind=kind,
            title=title,
            urgent=urgent,
            required_role=required_role(decisions),
            actions=actions,
            decisions=decisions,
            guest_message_preview=guest_message_preview,
            created_at=at,
        )
        self._tickets[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> ApprovalTicket:
        try:
            return self._tickets[ticket_id]
        except KeyError as exc:
            raise TicketNotFoundError(f"Không có yêu cầu duyệt {ticket_id}") from exc

    def all(self) -> tuple[ApprovalTicket, ...]:
        return tuple(self._tickets.values())

    def pending(self) -> tuple[ApprovalTicket, ...]:
        return tuple(ticket for ticket in self._tickets.values() if ticket.status == TicketStatus.PENDING)

    def pending_for(self, role: HumanRole) -> tuple[ApprovalTicket, ...]:
        return tuple(ticket for ticket in self.pending() if can_approve(role, ticket.required_role))

    def decide(
        self,
        ticket_id: str,
        *,
        role: HumanRole,
        actor_name: str,
        approved: bool,
        at: datetime,
        note: str = "",
    ) -> ApprovalTicket:
        ticket = self.get(ticket_id)
        if ticket.status != TicketStatus.PENDING:
            raise TicketAlreadyDecidedError(f"Yêu cầu {ticket_id} đã được xử lý")
        if not can_approve(role, ticket.required_role):
            raise ApprovalPermissionError(
                f"Vai trò {role.value} không có thẩm quyền duyệt {ticket_id} (cần {ticket.required_role.value})"
            )
        ticket.status = TicketStatus.APPROVED if approved else TicketStatus.REJECTED
        ticket.decided_at = at
        ticket.decided_by = actor_name
        ticket.decided_role = role
        ticket.note = note
        return ticket
