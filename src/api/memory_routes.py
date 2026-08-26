from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.models import Memory, User, Workspace
from src.db.session import get_db
from src.models.memory_schemas import MemoryCreateRequest, MemoryOut, MemoryUpdateRequest
from src.services import guardrail_service, memory_service
from src.services.workspace_service import resolve_workspace_for_user

router = APIRouter()


def _to_out(memory: Memory) -> MemoryOut:
    return MemoryOut(
        id=memory.id, category=memory.category, title=memory.title, detail=memory.detail,
        workspace_id=memory.workspace_id, memory_type=memory.memory_type,
        status=memory.status, source_type=memory.source_type,
        source_conversation_id=memory.source_conversation_id,
        source_message_ids=memory.source_message_ids or [], consent_scope_hash=memory.consent_scope_hash,
        sensitivity=memory.sensitivity, confidence=memory.confidence, importance=memory.importance,
        user_confirmed=memory.user_confirmed, expires_at=memory.expires_at,
        last_accessed_at=memory.last_accessed_at, created_at=memory.created_at, updated_at=memory.updated_at,
    )


async def _get_own_memory_or_404(memory_id: str, current_user: User, db: AsyncSession) -> Memory:
    memory = (
        await db.execute(select(Memory).where(Memory.id == memory_id, Memory.owner_id == current_user.id))
    ).scalar_one_or_none()
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    # Same workspace_id caveat as list_memories/list_tasks: an AI-extracted memory from a shared
    # personal-workspace conversation can legitimately carry a *different* participant's personal
    # workspace_id. owner_id above already proved this memory is this user's own - only
    # re-validate workspace membership for an organization workspace, where it's a real
    # multi-tenant boundary. Without this, editing/deleting such a memory raised
    # "Workspace access denied" for its own owner.
    workspace = await db.get(Workspace, memory.workspace_id)
    if workspace is not None and workspace.type == "organization":
        await resolve_workspace_for_user(db, current_user.id, memory.workspace_id)
    return memory


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    workspace_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_expired: bool = Query(default=False),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MemoryOut]:
    workspace = await resolve_workspace_for_user(db, current_user.id, workspace_id)
    # Same reasoning as task_routes.py's list_tasks: an AI-extracted memory from a shared
    # personal-workspace conversation gets workspace_id = conversation.workspace_id, anchored to
    # whichever participant's personal workspace created the conversation first - a different
    # personal workspace than this owner's own. Requiring an exact match here silently hid every
    # such memory from its own owner. Only enforce the match for an organization workspace.
    filters = [Memory.owner_id == current_user.id]
    if workspace.type == "organization":
        filters.append(Memory.workspace_id == workspace.id)
    stmt = select(Memory).where(*filters)
    if not include_expired:
        now = datetime.now(UTC)
        stmt = stmt.where(or_(Memory.expires_at.is_(None), Memory.expires_at > now))
    memories = (
        await db.execute(
            stmt
            .order_by(Memory.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return [_to_out(m) for m in memories]


@router.post("/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    request: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    if memory_service.is_forbidden_sensitive_memory(f"{request.title}\n{request.detail}"):
        raise HTTPException(status_code=422, detail="Không được lưu thông tin xác thực hoặc thuộc tính cá nhân nhạy cảm vào memory.")
    # This is an explicitly user-controlled CRUD operation, so validate its concrete content for
    # unsafe objectives/injection without requiring a neutral title to look like a chat-domain ask.
    decision = guardrail_service.evaluate_action_content(f"{request.title}\n{request.detail}")
    if not decision.allowed:
        raise HTTPException(status_code=422, detail=decision.reason)
    workspace = await resolve_workspace_for_user(db, current_user.id, request.workspace_id)
    memory = await memory_service.create_memory_from_request(
        db, current_user, workspace.id, request
    )
    return _to_out(memory)


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    memory = await _get_own_memory_or_404(memory_id, current_user, db)
    changes = request.model_dump(exclude_unset=True)
    candidate_title = changes.get("title", memory.title)
    candidate_detail = changes.get("detail", memory.detail)
    if memory_service.is_forbidden_sensitive_memory(f"{candidate_title}\n{candidate_detail}"):
        raise HTTPException(status_code=422, detail="Không được lưu thông tin xác thực hoặc thuộc tính cá nhân nhạy cảm vào memory.")
    decision = guardrail_service.evaluate_action_content(f"{candidate_title}\n{candidate_detail}")
    if not decision.allowed:
        raise HTTPException(status_code=422, detail=decision.reason)
    expires_at = changes.get("expires_at")
    if expires_at is not None:
        expires_at = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
        # An explicit past timestamp is a supported way for the user to expire a memory now.
        changes["expires_at"] = expires_at
    for field, value in changes.items():
        setattr(memory, field, value)
    if "title" in changes or "detail" in changes:
        await memory_service.prepare_embedding(memory)
    # A user editing/approving a proposed note makes the durable write explicit.
    if changes.get("status") == "active":
        memory.user_confirmed = True
        await memory_service.supersede_exact_conflicts(db, memory)
    await db.commit()
    await db.refresh(memory)
    return _to_out(memory)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    memory = await _get_own_memory_or_404(memory_id, current_user, db)
    await db.delete(memory)
    await db.commit()
