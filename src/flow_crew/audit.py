"""Nhật ký audit của FlowCrew: append-only, nối chuỗi hash.

Mọi đề xuất, phán quyết, phê duyệt và lần thực thi đều rơi vào đây. Mỗi bản ghi
mang hash của bản trước, nên sửa hay xoá một dòng sau đó sẽ làm `verify()` gãy
chứ không âm thầm viết lại lịch sử (US-8).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import Field

from src.flow_crew.contracts import FrozenContract

_GENESIS = "0" * 64


class AuditEntry(FrozenContract):
    seq: int = Field(ge=1)
    at: datetime
    actor: str
    event: str
    detail: str
    workflow_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str


def _digest(prev_hash: str, body: dict[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{prev_hash}|{payload}".encode()).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(
        self,
        *,
        at: datetime,
        actor: str,
        event: str,
        detail: str,
        workflow_id: str | None = None,
        **data: Any,
    ) -> AuditEntry:
        prev_hash = self._entries[-1].hash if self._entries else _GENESIS
        body = {
            "seq": len(self._entries) + 1,
            "at": at.isoformat(),
            "actor": actor,
            "event": event,
            "detail": detail,
            "workflow_id": workflow_id,
            "data": data,
        }
        entry = AuditEntry(
            seq=body["seq"],
            at=at,
            actor=actor,
            event=event,
            detail=detail,
            workflow_id=workflow_id,
            data=data,
            prev_hash=prev_hash,
            hash=_digest(prev_hash, body),
        )
        self._entries.append(entry)
        return entry

    def entries(self, *, workflow_id: str | None = None) -> tuple[AuditEntry, ...]:
        if workflow_id is None:
            return tuple(self._entries)
        return tuple(entry for entry in self._entries if entry.workflow_id == workflow_id)

    def verify(self) -> bool:
        prev_hash = _GENESIS
        for entry in self._entries:
            body = {
                "seq": entry.seq,
                "at": entry.at.isoformat(),
                "actor": entry.actor,
                "event": entry.event,
                "detail": entry.detail,
                "workflow_id": entry.workflow_id,
                "data": entry.data,
            }
            if entry.prev_hash != prev_hash or entry.hash != _digest(prev_hash, body):
                return False
            prev_hash = entry.hash
        return True
