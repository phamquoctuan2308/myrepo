from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    sender: str | None = Field(default=None, max_length=200)
    content: str = Field(..., max_length=10_000)
    timestamp: str | None = Field(default=None, max_length=64, description="ISO 8601 datetime, optional")


class MessageScope(BaseModel):
    kind: Literal["latest_n", "unread", "today", "yesterday", "this_week", "rolling_hours", "custom_range"]
    count: int | None = Field(default=None, ge=1, le=50)
    hours: int | None = Field(default=None, ge=1, le=168)
    since: datetime | None = None
    until: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_fields(self):
        if self.kind == "custom_range" and (self.since is None or self.until is None):
            raise ValueError("custom_range requires both since and until")
        if self.since and self.until and self.since >= self.until:
            raise ValueError("scope since must be before until")
        return self


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ user")
    thread_id: str | None = Field(
        default=None, max_length=128, description="Conversation thread id; generated if omitted"
    )
    workspace_id: str | None = Field(default=None, description="Active workspace for workspace-scoped agent tools")
    context_limit: int = Field(default=20, ge=1, le=50)
    scope: MessageScope | None = None
    quick_action: Literal["summarize", "extract_tasks"] | None = Field(
        default=None,
        description=(
            "Set by AIPanel's deterministic Quick Actions (Summarize/Extract tasks) so the server "
            "skips the planner's LLM call and the whole LangGraph run - the planner always routes "
            "these two to the same tool anyway. `message` is still required (kept for display/"
            "backwards compat) but is ignored when this is set."
        ),
    )
    messages: list[ChatMessage] | None = Field(
        default=None,
        max_length=200,
        description="Raw message history to summarize (read by summarize_conversation via state)",
    )
    conversation_id: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "If `messages` come from a real 1-1/group chat conversation, its id - the server "
            "verifies the caller is actually a participant before letting the agent see them, "
            "rather than trusting whatever `messages` the client attached."
        ),
    )


class InterruptPayload(BaseModel):
    type: Literal[
        "calendar_event",
        "calendar_event_update",
        "calendar_event_delete",
        "reminder",
        "memory_write",
        "memory_delete",
    ]
    draft: dict


class AuthorizedContextMetadata(BaseModel):
    included_participants: list[str] = Field(default_factory=list)
    excluded_participants: list[str] = Field(default_factory=list)
    included_message_count: int = 0
    window_message_count: int = 0
    coverage: float = 0.0
    source_message_ids: list[str] = Field(default_factory=list)
    consent_scope_hash: str = ""


class ChatResponse(BaseModel):
    response: str = Field(default="", description="Phản hồi từ agent")
    analysis: str = Field(default="", description="Phân tích nội bộ")
    thread_id: str
    status: Literal["completed", "interrupted", "error"] = "completed"
    interrupt: InterruptPayload | None = None
    context_scope: AuthorizedContextMetadata | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    approved: bool
    edits: dict | None = None
