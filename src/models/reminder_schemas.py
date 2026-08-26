from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReminderOut(BaseModel):
    id: str
    workspace_id: str
    title: str
    message: str
    due_at: datetime
    fire_at: datetime
    status: Literal["scheduled", "fired", "cancelled"]
    source: Literal["manual", "agent", "proactive"]
    created_at: datetime
    updated_at: datetime


class ReminderCreateRequest(BaseModel):
    workspace_id: str | None = None
    title: str = Field(..., min_length=1, max_length=200)
    due_at_iso: datetime
    lead_minutes: int = Field(default=30, ge=0, le=10080)
    message: str = Field(default="", max_length=2000)
