from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import session as db_session
from src.db.models import Conversation, Memory, MemoryEpisode, User, Workspace
from src.models.memory_schemas import MemoryCreateRequest
from src.services import chat_service, consent_service
from src.services.authorization_service import require_conversation_access


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def is_expired(memory: Memory, now: datetime | None = None) -> bool:
    if memory.expires_at is None:
        return False
    return _utc(memory.expires_at) <= (now or datetime.now(UTC))


async def validate_memory_source(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    workspace_id: str,
    source_message_ids: list[str],
    consent_scope_hash: str,
) -> None:
    await require_conversation_access(db, user, conversation_id, "viewer")
    await chat_service.assert_ai_permission(db, conversation_id, user.id)
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    # Same reasoning as src/api/routes.py's /chat handler and task_routes.create_task: a
    # personal-workspace direct/group conversation is anchored to whichever participant's
    # personal workspace created it first, so the OTHER participant's own `workspace_id` here is
    # legitimately a different personal workspace. Only reject when it would actually matter.
    if conversation.workspace_id != workspace_id:
        target_workspace = await db.get(Workspace, workspace_id)
        if target_workspace is not None and target_workspace.type == "organization":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Memory source does not belong to the selected workspace",
            )
    current_hash = await consent_service.get_consent_scope_hash(db, conversation_id)
    if current_hash != consent_scope_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation AI consent changed; create the memory from fresh context",
        )
    if not await consent_service.validate_authorized_source_ids(db, conversation_id, source_message_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Memory provenance includes a message that AI is not allowed to process",
        )


async def create_memory_from_request(
    db: AsyncSession,
    user: User,
    workspace_id: str,
    request: MemoryCreateRequest,
) -> Memory:
    if request.expires_at is not None and _utc(request.expires_at) <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expires_at must be in the future",
        )
    if request.source_conversation_id:
        await validate_memory_source(
            db,
            user,
            request.source_conversation_id,
            workspace_id,
            request.source_message_ids,
            request.consent_scope_hash or "",
        )
    memory = Memory(
        workspace_id=workspace_id,
        owner_id=user.id,
        category=request.category,
        title=request.title,
        detail=request.detail,
        memory_type=request.memory_type,
        source_conversation_id=request.source_conversation_id,
        source_message_ids=request.source_message_ids,
        consent_scope_hash=request.consent_scope_hash,
        sensitivity=request.sensitivity,
        confidence=request.confidence,
        importance=request.importance,
        expires_at=request.expires_at,
        status="active",
        source_type="manual",
        user_confirmed=True,
        provenance={"actor": "user", "channel": "memory_page"},
    )
    await prepare_embedding(memory)
    db.add(memory)
    await supersede_exact_conflicts(db, memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def search_active_memories(
    db: AsyncSession,
    *,
    owner_id: str,
    workspace_id: str,
    query: str = "",
    memory_types: set[str] | None = None,
    limit: int = 10,
) -> list[Memory]:
    now = datetime.now(UTC)
    owner = await db.get(User, owner_id)
    if owner is None or not owner.is_active:
        return []
    stmt = select(Memory).where(
        Memory.owner_id == owner_id,
        Memory.workspace_id == workspace_id,
        or_(Memory.expires_at.is_(None), Memory.expires_at > now),
    )
    if memory_types:
        stmt = stmt.where(Memory.memory_type.in_(memory_types))
    if query.strip():
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Memory.title.ilike(pattern),
                Memory.detail.ilike(pattern),
                Memory.category.ilike(pattern),
            )
        )
    candidates = list(
        (await db.execute(stmt.order_by(Memory.updated_at.desc()).limit(max(1, min(limit * 3, 50))))).scalars()
    )
    active: list[Memory] = []
    for memory in candidates:
        if memory.source_conversation_id:
            try:
                await require_conversation_access(db, owner, memory.source_conversation_id, "viewer")
            except HTTPException:
                continue
            current_hash = await consent_service.get_consent_scope_hash(db, memory.source_conversation_id)
            if current_hash != memory.consent_scope_hash:
                continue
            if not await consent_service.validate_authorized_source_ids(
                db, memory.source_conversation_id, memory.source_message_ids
            ):
                continue
        memory.last_accessed_at = now
        active.append(memory)
        if len(active) >= limit:
            break
    if active:
        await db.commit()
    return active


_WORD_RE = re.compile(r"[a-z0-9_]+")
_FORBIDDEN_MEMORY_RE = re.compile(
    r"\b(password|mat\s*khau|passcode|otp|api[_ -]?key|secret|access[_ -]?token|"
    r"refresh[_ -]?token|private[_ -]?key|cvv|so\s*the|cccd|cmnd|ho\s*chieu|"
    r"social\s*security|bank\s*account|tai\s*khoan\s*ngan\s*hang|sinh\s*trac|biometric|"
    r"ton\s*giao|religion|xu\s*huong\s*tinh\s*duc|sexual\s*orientation|"
    r"dang\s*phai|political\s*affiliation|chan\s*doan|diagnos(?:is|ed))\b"
)


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(_normalize_text(text)))


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def content_hash(title: str, detail: str) -> str:
    canonical = " ".join(f"{title}\n{detail}".lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_forbidden_sensitive_memory(text: str) -> bool:
    return bool(_FORBIDDEN_MEMORY_RE.search(_normalize_text(text)))


async def embed_text(text: str) -> tuple[list[float] | None, str | None]:
    """Best-effort embeddings. Recall still works lexically when no embedding key is configured."""
    from src.config import get_settings

    settings = get_settings()
    if settings.app_env == "test":
        return None, None
    try:
        if settings.google_api_key:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            model = "models/gemini-embedding-001"
            vector = await GoogleGenerativeAIEmbeddings(
                model=model, google_api_key=settings.google_api_key
            ).aembed_query(text)
            return list(vector), model
        if settings.openai_api_key:
            from langchain_openai import OpenAIEmbeddings

            model = "text-embedding-3-small"
            vector = await OpenAIEmbeddings(model=model, api_key=settings.openai_api_key).aembed_query(text)
            return list(vector), model
    except Exception:  # embedding is an enhancement; CRUD/chat must not fail when provider is down
        return None, None
    return None, None


def _cosine(left: list | None, right: list | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    norm = math.sqrt(sum(float(a) ** 2 for a in left)) * math.sqrt(sum(float(b) ** 2 for b in right))
    return dot / norm if norm else 0.0


def _relevance(query: str, text: str, vector: list | None, query_vector: list | None,
               importance: float, created_at: datetime) -> float:
    query_words, text_words = _words(query), _words(text)
    lexical = len(query_words & text_words) / max(1, len(query_words))
    semantic = max(0.0, _cosine(vector, query_vector))
    age_days = max(0.0, (datetime.now(UTC) - _utc(created_at)).total_seconds() / 86_400)
    recency = 1 / (1 + age_days / 30)
    return 0.45 * semantic + 0.30 * lexical + 0.15 * float(importance) + 0.10 * recency


async def list_memories_for_owner(
    owner_id: str | None, *, include_pending: bool = True, limit: int = 100
) -> list[Memory]:
    """All memory notes for a user, newest first. Shared by memory_routes.py's `GET /memories` and
    the agent's `list_memories` tool (src/agents/tools/memory_tool.py)."""
    async with db_session.async_session_maker() as db:
        memories = (
            await db.execute(
                select(Memory)
                .where(
                    Memory.owner_id == owner_id,
                    Memory.status.in_(["active", "pending_review"] if include_pending else ["active"]),
                    or_(Memory.expires_at.is_(None), Memory.expires_at > datetime.now(UTC)),
                )
                .order_by(Memory.updated_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return list(memories)


async def supersede_exact_conflicts(db: AsyncSession, incoming: Memory) -> int:
    """Retire an explicitly replaced durable note without deleting its provenance.

    Two notes conflict only when the same user writes the same category/type/title again; this is
    an exact identity key, never an LLM inference. Callers invoke it only after an explicit user
    write or approval, so an automatic heartbeat candidate cannot overwrite user memory.
    """
    await db.flush()
    conflicts = (
        await db.execute(
            select(Memory).where(
                Memory.owner_id == incoming.owner_id,
                Memory.category == incoming.category,
                Memory.memory_type == incoming.memory_type,
                Memory.title == incoming.title,
                Memory.id != incoming.id,
                Memory.status == "active",
            )
        )
    ).scalars().all()
    for existing in conflicts:
        existing.status = "superseded"
        provenance = dict(existing.provenance or {})
        provenance.update(
            {
                "superseded_by": incoming.id,
                "superseded_at": datetime.now(UTC).isoformat(),
                "supersession_reason": "explicit_user_write",
            }
        )
        existing.provenance = provenance
    return len(conflicts)


async def retrieve_memories(owner_id: str | None, query: str, *, limit: int = 6) -> list[Memory]:
    if not owner_id:
        return []
    memories = await list_memories_for_owner(owner_id, include_pending=False, limit=250)
    if not memories:
        return []
    query_vector, _ = await embed_text(query) if query.strip() else (None, None)
    ranked = sorted(
        memories,
        key=lambda m: _relevance(
            query, f"{m.category} {m.title} {m.detail}", m.embedding, query_vector,
            m.importance, m.updated_at or m.created_at,
        ),
        reverse=True,
    )[:limit]
    # Access metadata is deliberately best effort and never affects the response transaction.
    async with db_session.async_session_maker() as db:
        now = datetime.now(UTC)
        for item in ranked:
            owned = await db.get(Memory, item.id)
            if owned:
                owned.access_count += 1
                owned.last_accessed_at = now
        await db.commit()
    return ranked


async def retrieve_episodes(owner_id: str | None, query: str, *, limit: int = 4) -> list[MemoryEpisode]:
    if not owner_id:
        return []
    now = datetime.now(UTC)
    async with db_session.async_session_maker() as db:
        rows = (
            await db.execute(
                select(MemoryEpisode)
                .where(
                    MemoryEpisode.owner_id == owner_id,
                    or_(MemoryEpisode.expires_at.is_(None), MemoryEpisode.expires_at > now),
                )
                .order_by(MemoryEpisode.created_at.desc())
                .limit(100)
            )
        ).scalars().all()
    query_vector, _ = await embed_text(query) if query.strip() else (None, None)
    return sorted(
        rows,
        key=lambda e: _relevance(
            query, f"{e.summary} {' '.join(e.decisions or [])} {' '.join(e.open_loops or [])}",
            e.embedding, query_vector, e.importance, e.created_at,
        ),
        reverse=True,
    )[:limit]


async def prepare_embedding(memory: Memory) -> None:
    memory.content_hash = content_hash(memory.title, memory.detail or "")
    vector, model = await embed_text(f"{memory.category}: {memory.title}\n{memory.detail}")
    memory.embedding, memory.embedding_model = vector, model
