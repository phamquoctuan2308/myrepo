from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AIPermission,
    Conversation,
    ConversationParticipant,
    ConversationRollingSummary,
    EventCandidate,
    EventExtractionCursor,
    Memory,
    MemoryEpisode,
    Message,
    Task,
    User,
    WorkspaceMembership,
)
from src.models.auth_schemas import UserPublic
from src.models.chat_schemas import ConversationSummary, MessageOut
from src.services.authorization_service import (
    get_authorized_participant_ids,
    require_conversation_access,
    require_workspace_member,
)
from src.services.workspace_service import resolve_workspace_for_user


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def serialize_message(message: Message, sender: User) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=sender.display_name,
        content=message.content,
        created_at=_iso(message.created_at),
    )


async def assert_participant(db: AsyncSession, conversation_id: str, user_id: str) -> ConversationParticipant:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversation access denied")
    participant = await require_conversation_access(db, user, conversation_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversation access denied")
    return participant


async def get_participant_ids(db: AsyncSession, conversation_id: str) -> list[str]:
    return await get_authorized_participant_ids(db, conversation_id)


async def get_ai_permission(db: AsyncSession, conversation_id: str, user_id: str) -> AIPermission | None:
    return (
        await db.execute(
            select(AIPermission).where(
                AIPermission.conversation_id == conversation_id,
                AIPermission.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def set_ai_permission(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    granted: bool | None = None,
    contribution_allowed: bool | None = None,
) -> AIPermission:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is not None and conversation.type == "group":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group AI is controlled by a conversation manager",
        )
    permission = await get_ai_permission(db, conversation_id, user_id)
    changed = permission is None
    contribution_revoked = False
    if permission is None:
        permission = AIPermission(
            conversation_id=conversation_id,
            user_id=user_id,
            granted=bool(granted),
            contribution_allowed=bool(contribution_allowed),
        )
        db.add(permission)
    else:
        if granted is not None and permission.granted != granted:
            permission.granted = granted
            changed = True
        if contribution_allowed is not None and permission.contribution_allowed != contribution_allowed:
            contribution_revoked = permission.contribution_allowed and not contribution_allowed
            permission.contribution_allowed = contribution_allowed
            changed = True
    if changed:
        permission.updated_at = datetime.now(UTC)

    # A manual extraction depends on the complete authorized view, so any real scope change makes
    # its unconfirmed candidates stale.  A proactive candidate only depends on its source author
    # and is invalidated specifically when that author revokes contribution processing.
    if changed:
        await db.execute(
            update(Task)
            .where(
                Task.conversation_id == conversation_id,
                Task.status == "suggested",
                Task.source == "ai_extracted",
            )
            .values(status="invalidated", invalidated_reason="consent_scope_changed")
        )
    if contribution_revoked:
        await db.execute(
            update(Task)
            .where(
                Task.conversation_id == conversation_id,
                Task.status == "suggested",
                Task.source_sender_id == user_id,
            )
            .values(status="invalidated", invalidated_reason="source_consent_revoked")
        )
        # The rolling conversation summary is a persisted artifact re-injected into every future
        # agent turn - unlike a live per-request read, it can't just stop selecting this sender's
        # messages going forward. Flag it for a full rebuild so already-baked prose from the
        # revoked sender doesn't keep circulating. No-op if no row exists yet.
        await db.execute(
            update(ConversationRollingSummary)
            .where(ConversationRollingSummary.conversation_id == conversation_id)
            .values(needs_reset=True)
        )
    await db.commit()
    await db.refresh(permission)
    return permission


async def assert_ai_permission(db: AsyncSession, conversation_id: str, user_id: str) -> None:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.type == "group":
        if not conversation.ai_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI is not enabled by this conversation's manager",
            )
        return
    permission = await get_ai_permission(db, conversation_id, user_id)
    if permission is None or not permission.granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="AI permission not granted for this conversation"
        )


async def set_group_ai_policy(
    db: AsyncSession,
    conversation_id: str,
    actor: User,
    enabled: bool,
) -> Conversation:
    """Change the one group-wide AI policy; only a conversation manager may do this."""
    await require_conversation_access(db, actor, conversation_id, "manager")
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.type != "group":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group AI policy only applies to group conversations",
        )
    if conversation.ai_enabled == enabled:
        return conversation

    now = datetime.now(UTC)
    conversation.ai_enabled = enabled
    conversation.ai_policy_version += 1
    conversation.ai_enabled_by_user_id = actor.id if enabled else None
    conversation.ai_enabled_at = now if enabled else None
    # Any unconfirmed output was derived under the previous authorization policy.  Confirmed
    # tasks/calendar events are domain records and are not silently deleted.
    await db.execute(
        update(Task)
        .where(Task.conversation_id == conversation_id, Task.status == "suggested")
        .values(status="invalidated", invalidated_reason="group_ai_policy_changed")
    )
    cursor = await db.get(EventExtractionCursor, conversation_id)
    if cursor is not None:
        cursor.last_message_created_at = None
        cursor.last_message_id = None
        cursor.processed_message_count = 0
        cursor.status = "idle"
        cursor.last_error = None
    await db.execute(
        update(EventCandidate)
        .where(EventCandidate.conversation_id == conversation_id, EventCandidate.status == "suggested")
        .values(status="invalidated", invalidated_reason="group_ai_policy_changed")
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def create_message(db: AsyncSession, conversation_id: str, sender_id: str, content: str) -> Message:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    message = Message(conversation_id=conversation_id, sender_id=sender_id, content=content)
    db.add(message)
    conversation.updated_at = datetime.now(UTC)
    await db.execute(
        update(ConversationParticipant)
        .where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.revoked_at.is_(None),
        )
        .values(hidden_at=None)
    )
    await db.commit()
    await db.refresh(message)
    return message


async def hide_conversation(db: AsyncSession, conversation_id: str, user_id: str) -> None:
    participant = await assert_participant(db, conversation_id, user_id)
    participant.hidden_at = datetime.now(UTC)
    await db.commit()


async def leave_group_conversation(
    db: AsyncSession, conversation_id: str, user: User
) -> tuple[list[str], bool]:
    participant = await assert_participant(db, conversation_id, user.id)
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.type != "group":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Direct conversations cannot be left")

    now = datetime.now(UTC)
    participant.revoked_at = now
    participant.hidden_at = now
    permission = await get_ai_permission(db, conversation_id, user.id)
    if permission is not None:
        await db.delete(permission)

    remaining = list(
        (
            await db.execute(
                select(ConversationParticipant)
                .where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.user_id.is_not(None),
                    ConversationParticipant.user_id != user.id,
                    ConversationParticipant.revoked_at.is_(None),
                )
                .order_by(ConversationParticipant.joined_at, ConversationParticipant.id)
            )
        ).scalars()
    )
    if not remaining:
        # Preserve confirmed user-owned domain records, but detach them from the chat that no
        # longer has any authorized reader. Derived conversation-only artifacts are deleted
        # explicitly because existing production foreign keys do not define database cascades.
        await db.execute(update(Task).where(Task.conversation_id == conversation_id).values(conversation_id=None))
        await db.execute(
            update(Memory)
            .where(Memory.source_conversation_id == conversation_id)
            .values(source_conversation_id=None)
        )
        await db.execute(
            update(MemoryEpisode)
            .where(MemoryEpisode.conversation_id == conversation_id)
            .values(conversation_id=None)
        )
        await db.execute(delete(AIPermission).where(AIPermission.conversation_id == conversation_id))
        await db.execute(delete(EventCandidate).where(EventCandidate.conversation_id == conversation_id))
        await db.execute(delete(EventExtractionCursor).where(EventExtractionCursor.conversation_id == conversation_id))
        await db.execute(
            delete(ConversationRollingSummary).where(
                ConversationRollingSummary.conversation_id == conversation_id
            )
        )
        await db.delete(conversation)
        await db.commit()
        return [], True

    if participant.resource_role == "manager" and not any(row.resource_role == "manager" for row in remaining):
        remaining[0].resource_role = "manager"
    conversation.ai_policy_version += 1
    conversation.updated_at = now
    await db.execute(
        update(Task)
        .where(Task.conversation_id == conversation_id, Task.status == "suggested")
        .values(status="invalidated", invalidated_reason="conversation_membership_changed")
    )
    await db.execute(
        update(EventCandidate)
        .where(EventCandidate.conversation_id == conversation_id, EventCandidate.status == "suggested")
        .values(status="invalidated", invalidated_reason="conversation_membership_changed")
    )
    # A group's readable/eligible set is all-or-nothing while ai_enabled stays on (see
    # proactive_service._permission_scope) - a participant leaving is the only way that roster can
    # shrink without also flipping ai_enabled off. Same rebuild-on-shrink reasoning as
    # set_ai_permission's contribution_revoked branch.
    await db.execute(
        update(ConversationRollingSummary)
        .where(ConversationRollingSummary.conversation_id == conversation_id)
        .values(needs_reset=True)
    )
    await db.commit()
    return [row.user_id for row in remaining if row.user_id], False


async def mark_read(db: AsyncSession, conversation_id: str, user_id: str) -> None:
    participant = await assert_participant(db, conversation_id, user_id)
    participant.last_read_at = datetime.now(UTC)
    await db.commit()


async def get_first_unread_message_id(db: AsyncSession, conversation_id: str, user_id: str) -> str | None:
    """Return the oldest unread message from another participant."""
    participant = await assert_participant(db, conversation_id, user_id)
    return (
        await db.execute(
            select(Message.id)
            .where(
                Message.conversation_id == conversation_id,
                Message.created_at > participant.last_read_at,
                Message.sender_id != user_id,
            )
            .order_by(Message.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _assert_workspace_participants(
    db: AsyncSession,
    workspace_id: str,
    user_ids: set[str],
) -> None:
    if not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one participant is required")
    rows = (
        (
            await db.execute(
                select(WorkspaceMembership.user_id).where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id.in_(user_ids),
                    WorkspaceMembership.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    if set(rows) != user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Participant is outside the workspace")


async def get_or_create_direct_conversation(
    db: AsyncSession,
    user_a_id: str,
    user_b_id: str,
    workspace_id: str | None = None,
) -> Conversation:
    if user_a_id == user_b_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create a conversation with self")
    # workspace_id is optional from the client - resolve_workspace_for_user falls back to the
    # caller's personal workspace, same default used by GET /users and GET /conversations.
    workspace = await resolve_workspace_for_user(db, user_a_id, workspace_id)
    if workspace.type == "organization":
        await require_workspace_member(db, await db.get(User, user_a_id), workspace.id)
        await _assert_workspace_participants(db, workspace.id, {user_a_id, user_b_id})
    else:
        # Personal workspaces have no membership roster to scope by - plain 1:1 chat between
        # any two active users. workspace.id is stored on the Conversation row only because
        # workspace_id is a required FK slot; it does not restrict who can see the conversation
        # (see list_conversations, which does not filter personal-workspace results by it).
        other = await db.get(User, user_b_id)
        if other is None or not other.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active user not found")

    # Personal-workspace conversations aren't anchored to a single shared workspace_id (each
    # side's own personal workspace differs), so dedup by participant pair across all of the
    # caller's direct conversations rather than scoping the search to one workspace_id.
    candidate_query = (
        select(ConversationParticipant.conversation_id)
        .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
        .where(
            Conversation.type == "direct",
            ConversationParticipant.user_id == user_a_id,
            ConversationParticipant.revoked_at.is_(None),
        )
    )
    if workspace.type == "organization":
        candidate_query = candidate_query.where(Conversation.workspace_id == workspace.id)
    candidate_ids = (await db.execute(candidate_query)).scalars().all()
    for cid in candidate_ids:
        participant_ids = (
            (
                await db.execute(
                    select(ConversationParticipant.user_id).where(
                        ConversationParticipant.conversation_id == cid,
                        ConversationParticipant.revoked_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if set(participant_ids) == {user_a_id, user_b_id}:
            return await db.get(Conversation, cid)

    conversation = Conversation(workspace_id=workspace.id, type="direct", name=None, created_by=user_a_id)
    db.add(conversation)
    await db.flush()
    db.add_all(
        [
            ConversationParticipant(
                conversation_id=conversation.id,
                user_id=user_a_id,
                principal_kind="workspace_user",
                resource_role="manager",
                invited_by_user_id=user_a_id,
            ),
            ConversationParticipant(
                conversation_id=conversation.id,
                user_id=user_b_id,
                principal_kind="workspace_user",
                resource_role="participant",
                invited_by_user_id=user_a_id,
            ),
        ]
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def create_group_conversation(
    db: AsyncSession,
    creator_id: str,
    member_ids: list[str],
    name: str,
    workspace_id: str | None = None,
) -> Conversation:
    workspace = await resolve_workspace_for_user(db, creator_id, workspace_id)
    if workspace.type == "organization":
        await _assert_workspace_participants(db, workspace.id, {creator_id, *member_ids})
    else:
        # Personal workspace: no membership roster - any active user can be added directly.
        rows = (
            await db.execute(select(User.id).where(User.id.in_(member_ids), User.is_active.is_(True)))
        ).scalars().all()
        if set(rows) != set(member_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active user not found")
    conversation = Conversation(workspace_id=workspace.id, type="group", name=name, created_by=creator_id)
    db.add(conversation)
    await db.flush()
    all_member_ids = {creator_id, *member_ids}
    db.add_all(
        [
            ConversationParticipant(
                conversation_id=conversation.id,
                user_id=member_id,
                principal_kind="workspace_user",
                resource_role="manager" if member_id == creator_id else "participant",
                invited_by_user_id=creator_id,
            )
            for member_id in all_member_ids
        ]
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def build_conversation_summary(
    db: AsyncSession, conversation: Conversation, current_user_id: str
) -> ConversationSummary:
    participant_rows = (
        await db.execute(
            select(User, ConversationParticipant)
            .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
            .where(
                ConversationParticipant.conversation_id == conversation.id,
                ConversationParticipant.revoked_at.is_(None),
            )
        )
    ).all()
    participants = [
        UserPublic(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            platform_role=user.platform_role,
        )
        for user, _ in participant_rows
    ]
    my_participant = next((cp for _, cp in participant_rows if cp.user_id == current_user_id), None)

    if conversation.type == "group":
        name = conversation.name or "Group"
    else:
        other = next((user for user, _ in participant_rows if user.id != current_user_id), None)
        name = other.display_name if other else "Direct message"

    last_message_row = (
        await db.execute(
            select(Message, User)
            .join(User, User.id == Message.sender_id)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
    ).first()
    last_message = serialize_message(last_message_row[0], last_message_row[1]) if last_message_row else None

    unread_count = 0
    if my_participant is not None:
        unread_count = (
            await db.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conversation.id,
                    Message.created_at > my_participant.last_read_at,
                    Message.sender_id != current_user_id,
                )
            )
        ).scalar_one()

    if conversation.type == "group":
        ai_permission_granted = conversation.ai_enabled
    else:
        permission = await get_ai_permission(db, conversation.id, current_user_id)
        ai_permission_granted = permission.granted if permission is not None else False

    return ConversationSummary(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        type=conversation.type,
        name=name,
        participants=participants,
        last_message=last_message,
        unread_count=unread_count,
        ai_permission_granted=ai_permission_granted,
        updated_at=_iso(conversation.updated_at),
        my_resource_role=my_participant.resource_role if my_participant else None,
        ai_enabled=conversation.ai_enabled,
    )
