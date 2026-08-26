from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.models.auth_schemas import UserPublic


class ConversationCreateRequest(BaseModel):
    type: Literal["direct", "group"]
    participant_ids: list[str] = Field(..., min_length=1)
    name: str | None = None
    workspace_id: str | None = None


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    content: str
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    workspace_id: str
    type: Literal["direct", "group"]
    name: str
    participants: list[UserPublic]
    last_message: MessageOut | None
    unread_count: int
    ai_permission_granted: bool
    updated_at: str
    my_resource_role: Literal["manager", "participant", "viewer"] | None = None
    ai_enabled: bool = False


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class MessageListResponse(BaseModel):
    messages: list[MessageOut]
    has_more: bool
    # Only computed on the initial fetch (no `before` cursor) - see chat_routes.get_messages.
    first_unread_message_id: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class AIPermissionOut(BaseModel):
    conversation_id: str
    granted: bool
    contribution_allowed: bool
    updated_at: str | None = None
    mode: Literal["individual", "group_managed"] = "individual"
    can_manage: bool = False


class GroupAIPolicyUpdateRequest(BaseModel):
    enabled: bool


class AIPermissionUpdateRequest(BaseModel):
    granted: bool | None = None
    contribution_allowed: bool | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if self.granted is None and self.contribution_allowed is None:
            raise ValueError("At least one AI permission field must be provided")
        return self
