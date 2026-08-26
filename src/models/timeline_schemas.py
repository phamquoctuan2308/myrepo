from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TimelineKind = Literal["message", "task", "reminder", "calendar"]


class TimelineItem(BaseModel):
    id: str
    kind: TimelineKind
    occurred_at: datetime
    end_at: datetime | None = None
    title: str
    detail: str = ""
    status: str
    source_id: str
    conversation_id: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    url: str | None = None


class TimelineSourceStatus(BaseModel):
    source: TimelineKind
    status: Literal["ok", "unavailable", "not_connected"]
    item_count: int = 0
    detail: str | None = None


class PersonalTimelineOut(BaseModel):
    workspace_id: str
    timezone: str
    from_at: datetime
    to_at: datetime
    items: list[TimelineItem]
    sources: list[TimelineSourceStatus]
