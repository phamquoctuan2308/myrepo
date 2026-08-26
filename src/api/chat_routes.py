from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.models import Conversation, ConversationParticipant, Message, User, WorkspaceMembership
from src.db.session import get_db
from src.models.auth_schemas import UserPublic
from src.models.chat_schemas import (
    AIPermissionOut,
    AIPermissionUpdateRequest,
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationSummary,
    GroupAIPolicyUpdateRequest,
    MessageListResponse,
    MessageOut,
    SendMessageRequest,
)
from src.services import chat_service, event_extraction_service, proactive_service
from src.services.authorization_service import require_conversation_access
from src.services.workspace_service import resolve_workspace_for_user
from src.websocket.manager import manager

router = APIRouter()


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    search: str | None = Query(default=None),
    workspace_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserPublic]:
    workspace = await resolve_workspace_for_user(db, current_user.id, workspace_id)
    # Personal workspaces can start a direct chat with another registered user, but never expose
    # a bulk global email directory. Require an intentional search and cap discovery results.
    if workspace.type == "personal":
        if not search or len(search.strip()) < 2:
            return []
        stmt = select(User).where(User.id != current_user.id, User.is_active.is_(True))
        escaped_search = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_search}%"
        stmt = stmt.where(
            or_(
                User.display_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
        users = (await db.execute(stmt.order_by(User.display_name).limit(20))).scalars().all()
        return [
            UserPublic(
                id=u.id,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                platform_role=u.platform_role,
            )
            for u in users
        ]

    current_membership = (
        await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == current_user.id,
                WorkspaceMembership.status == "active",
            )
        )
    ).scalar_one_or_none()
    if current_membership is None or current_membership.role == "guest":
        return []
    member_ids = select(WorkspaceMembership.user_id).where(
        WorkspaceMembership.workspace_id == workspace.id,
        WorkspaceMembership.status == "active",
    )
    stmt = select(User).where(User.id != current_user.id, User.id.in_(member_ids), User.is_active.is_(True))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(User.display_name.ilike(pattern), User.email.ilike(pattern)))
    users = (await db.execute(stmt)).scalars().all()
    return [
        UserPublic(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            platform_role=u.platform_role,
        )
        for u in users
    ]


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    workspace_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    workspace = await resolve_workspace_for_user(db, current_user.id, workspace_id)
    participant_stmt = select(ConversationParticipant.conversation_id).where(
        ConversationParticipant.user_id == current_user.id,
        ConversationParticipant.revoked_at.is_(None),
        ConversationParticipant.hidden_at.is_(None),
    )
    if workspace.type == "organization":
        # Organization workspaces scope visibility to active membership in that workspace.
        participant_stmt = participant_stmt.join(
            WorkspaceMembership,
            (WorkspaceMembership.workspace_id == workspace.id) & (WorkspaceMembership.user_id == current_user.id),
        ).where(WorkspaceMembership.status == "active")
    # Personal workspaces have no membership roster, so every conversation the user actually
    # participates in counts - regardless of which side's personal workspace anchored it at
    # creation time (see chat_service.get_or_create_direct_conversation).
    conversation_ids = (await db.execute(participant_stmt)).scalars().all()
    conversations_stmt = select(Conversation).where(Conversation.id.in_(conversation_ids)).order_by(
        Conversation.updated_at.desc()
    )
    if workspace.type == "organization":
        conversations_stmt = conversations_stmt.where(Conversation.workspace_id == workspace.id)
    conversations = (await db.execute(conversations_stmt)).scalars().all()
    summaries = [await chat_service.build_conversation_summary(db, c, current_user.id) for c in conversations]
    return ConversationListResponse(conversations=summaries)


@router.post("/conversations", response_model=ConversationSummary)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummary:
    if request.type == "direct":
        if len(request.participant_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Direct conversations need exactly one other participant",
            )
        conversation = await chat_service.get_or_create_direct_conversation(
            db, current_user.id, request.participant_ids[0], request.workspace_id
        )
    else:
        if not request.name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group conversations require a name")
        conversation = await chat_service.create_group_conversation(
            db, current_user.id, request.participant_ids, request.name, request.workspace_id
        )
    return await chat_service.build_conversation_summary(db, conversation, current_user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: str,
    before: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    await require_conversation_access(db, current_user, conversation_id, "viewer")

    stmt = (
        select(Message, User).join(User, User.id == Message.sender_id).where(Message.conversation_id == conversation_id)
    )
    if before:
        before_message = await db.get(Message, before)
        if before_message is not None and before_message.conversation_id == conversation_id:
            stmt = stmt.where(Message.created_at < before_message.created_at)
    stmt = stmt.order_by(Message.created_at.desc()).limit(limit + 1)

    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    messages = [chat_service.serialize_message(m, u) for m, u in reversed(rows)]

    # Only worth computing on the initial page (no `before`) - that's the "just opened this
    # conversation" moment the frontend's jump-to-unread button anchors on; paginating further
    # back into history doesn't need it recomputed every time.
    first_unread_message_id = None
    if not before:
        first_unread_message_id = await chat_service.get_first_unread_message_id(db, conversation_id, current_user.id)

    return MessageListResponse(messages=messages, has_more=has_more, first_unread_message_id=first_unread_message_id)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    await require_conversation_access(db, current_user, conversation_id, "participant")
    message = await chat_service.create_message(db, conversation_id, current_user.id, request.content)
    message_out = chat_service.serialize_message(message, current_user)

    participant_ids = await chat_service.get_participant_ids(db, conversation_id)
    await manager.broadcast_to_users(participant_ids, {"type": "new_message", "message": message_out.model_dump()})
    background_tasks.add_task(
        proactive_service.maybe_suggest_task,
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=request.content,
        message_id=message.id,
    )
    background_tasks.add_task(
        event_extraction_service.maybe_extract_event_candidate,
        conversation_id=conversation_id,
        message_id=message.id,
    )
    return message_out


@router.get("/conversations/{conversation_id}/ai-permission", response_model=AIPermissionOut)
async def get_conversation_ai_permission(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIPermissionOut:
    participant = await chat_service.assert_participant(db, conversation_id, current_user.id)
    conversation = await db.get(Conversation, conversation_id)
    if conversation is not None and conversation.type == "group":
        return AIPermissionOut(
            conversation_id=conversation_id,
            granted=conversation.ai_enabled,
            contribution_allowed=conversation.ai_enabled,
            updated_at=conversation.ai_enabled_at.isoformat() if conversation.ai_enabled_at else None,
            mode="group_managed",
            can_manage=participant.resource_role == "manager",
        )
    permission = await chat_service.get_ai_permission(db, conversation_id, current_user.id)
    # can_manage has two unrelated meanings depending on mode: for "group_managed" it gates the
    # single group-wide ai_enabled toggle (real single-owner decision, manager-only). For
    # "individual" it instead gates managing this conversation's calendar-suggestion candidates
    # (Confirm/Dismiss/backfill) - a direct conversation has no "manager", and confirming always
    # writes to the confirming person's own calendar (see calendar_routes.confirm_event_candidate),
    # so every participant may act on their own behalf here.
    if permission is None:
        return AIPermissionOut(
            conversation_id=conversation_id,
            granted=False,
            contribution_allowed=False,
            updated_at=None,
            mode="individual",
            can_manage=True,
        )
    return AIPermissionOut(
        conversation_id=conversation_id,
        granted=permission.granted,
        contribution_allowed=permission.contribution_allowed,
        updated_at=permission.updated_at.isoformat(),
        mode="individual",
        can_manage=True,
    )


@router.put("/conversations/{conversation_id}/ai-permission", response_model=AIPermissionOut)
async def update_conversation_ai_permission(
    conversation_id: str,
    request: AIPermissionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIPermissionOut:
    await chat_service.assert_participant(db, conversation_id, current_user.id)
    permission = await chat_service.set_ai_permission(
        db,
        conversation_id,
        current_user.id,
        granted=request.granted,
        contribution_allowed=request.contribution_allowed,
    )
    return AIPermissionOut(
        conversation_id=conversation_id,
        granted=permission.granted,
        contribution_allowed=permission.contribution_allowed,
        updated_at=permission.updated_at.isoformat(),
        mode="individual",
        can_manage=True,
    )


@router.put("/conversations/{conversation_id}/ai-policy", response_model=AIPermissionOut)
async def update_group_ai_policy(
    conversation_id: str,
    request: GroupAIPolicyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIPermissionOut:
    conversation = await chat_service.set_group_ai_policy(
        db, conversation_id, current_user, request.enabled
    )
    participant_ids = await chat_service.get_participant_ids(db, conversation_id)
    await manager.broadcast_to_users(
        participant_ids,
        {
            "type": "group_ai_policy_changed",
            "conversation_id": conversation.id,
            "enabled": conversation.ai_enabled,
            "policy_version": conversation.ai_policy_version,
        },
    )
    return AIPermissionOut(
        conversation_id=conversation.id,
        granted=conversation.ai_enabled,
        contribution_allowed=conversation.ai_enabled,
        updated_at=conversation.ai_enabled_at.isoformat() if conversation.ai_enabled_at else None,
        mode="group_managed",
        can_manage=True,
    )


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await chat_service.mark_read(db, conversation_id, current_user.id)
    return {"status": "ok"}


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hide_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await chat_service.hide_conversation(db, conversation_id, current_user.id)


@router.post("/conversations/{conversation_id}/leave")
async def leave_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    remaining_user_ids, deleted = await chat_service.leave_group_conversation(
        db, conversation_id, current_user
    )
    if remaining_user_ids:
        await manager.broadcast_to_users(
            remaining_user_ids,
            {
                "type": "conversation_member_left",
                "conversation_id": conversation_id,
                "user_id": current_user.id,
            },
        )
    return {"status": "left", "conversation_deleted": deleted}
