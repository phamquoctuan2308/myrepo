"""HTTP surface của simulator FlowCrew.

Chỉ dùng cho mô phỏng: vai người duyệt đi vào từ request body — đúng thứ mà bản
production không bao giờ được phép tin. Trước khi FlowCrew chạy cho người dùng
thật, `role` phải lấy từ phiên đăng nhập đã xác thực.

Một engine cho mỗi tiến trình, đứng sau một khoá; engine chạy đồng bộ nên các
handler để `def` thường và FastAPI tự đẩy sang thread pool.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.flow_crew.approvals import (
    ApprovalPermissionError,
    TicketAlreadyDecidedError,
    TicketNotFoundError,
)
from src.flow_crew.clock import SimClock, at
from src.flow_crew.contracts import AgentId, HumanRole
from src.flow_crew.engine import (
    ApprovalBypassError,
    FlowCrewEngine,
    GovernanceBlockedError,
    IncidentStateError,
    WorkflowNotFoundError,
)
from src.flow_crew.mock_park import ParkDataError, ToolUnavailableError

router = APIRouter()

# Giờ mở màn của hero flow mục 7; reset đưa mô phỏng về đúng mốc này.
SIMULATION_START = at(14, 5)

InjectableTool = Literal["catalog", "app", "ops", "marketing", "ticketing", "booking", "telephony"]


class _Runtime:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.engine = FlowCrewEngine(clock=SimClock(SIMULATION_START))


_runtime = _Runtime()


def _locked(operation: Callable[[FlowCrewEngine], Any]) -> dict[str, Any]:
    with _runtime.lock:
        try:
            operation(_runtime.engine)
        except (ParkDataError, WorkflowNotFoundError, TicketNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ApprovalPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (TicketAlreadyDecidedError, IncidentStateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (GovernanceBlockedError, ApprovalBypassError) as exc:
            # Policy chặn không phải lỗi hệ thống: dashboard hiện đúng lý do.
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ToolUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _runtime.engine.snapshot()


class IncidentIn(BaseModel):
    closed_service_id: str = Field(default="SW-DOLPHIN", min_length=1, max_length=32)


class ApprovalDecisionIn(BaseModel):
    role: HumanRole
    actor_name: str = Field(min_length=1, max_length=80)
    approved: bool
    note: str = Field(default="", max_length=1_000)


class AskIn(BaseModel):
    agent: AgentId
    question: str = Field(min_length=1, max_length=500)
    guest_id: str | None = Field(default=None, max_length=16)


class InjectFailureIn(BaseModel):
    tool: InjectableTool
    times: int = Field(default=1, ge=1, le=5)


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    with _runtime.lock:
        return _runtime.engine.snapshot()


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    with _runtime.lock:
        return _runtime.engine.kpis()


@router.get("/roster")
def roster() -> dict[str, Any]:
    """A0 trả lời "ai trong đội đang phụ trách việc gì" (mục 6)."""

    from src.flow_crew.agents import crew_pm

    return {
        "roster": crew_pm.roster(),
        "agents": [
            {
                "agent": item.agent.value,
                "serves": item.serves,
                "does": list(item.does),
            }
            for item in crew_pm.REGISTRY
        ],
    }


@router.post("/simulation/reset")
def reset_simulation() -> dict[str, Any]:
    with _runtime.lock:
        _runtime.engine = FlowCrewEngine(clock=SimClock(SIMULATION_START))
        return _runtime.engine.snapshot()


@router.post("/simulation/inject-failure")
def inject_failure(body: InjectFailureIn) -> dict[str, Any]:
    return _locked(lambda engine: engine.park.inject_failure(body.tool, body.times))


@router.post("/incidents")
def open_incident(body: IncidentIn) -> dict[str, Any]:
    return _locked(lambda engine: engine.open_incident(closed_service_id=body.closed_service_id))


@router.post("/approvals/{ticket_id}/decision")
def approval_decision(ticket_id: str, body: ApprovalDecisionIn) -> dict[str, Any]:
    return _locked(
        lambda engine: engine.decide(
            ticket_id,
            role=body.role,
            actor_name=body.actor_name,
            approved=body.approved,
            note=body.note,
        )
    )


@router.post("/ask")
def ask(body: AskIn) -> dict[str, Any]:
    """US-1: hỏi thẳng một agent, không cần có sự cố nào đang chạy."""

    with _runtime.lock:
        try:
            answer = _runtime.engine.ask(body.agent, body.question, guest_id=body.guest_id)
        except ParkDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"agent": answer.agent.value, "text": answer.text, "data": answer.data}
