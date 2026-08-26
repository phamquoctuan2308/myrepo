from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import interrupt
from sqlalchemy import select

from src.agents.state import AgentState
from src.db import session as db_session
from src.db.models import Memory
from src.services import guardrail_service, memory_service


@tool
async def list_memories(
    query: str = "", limit: int = 10,
    state: Annotated[AgentState, InjectedState] = None,  # type: ignore[assignment]
) -> str:
    """List things the user has explicitly asked Orbit to remember about them (preferences,
    habits, people they work with, etc. - from the /memory page). This is long-term personal
    memory the user manages themselves, distinct from this conversation's own chat history. Use it
    to answer questions like "what do you remember about how I work" or to personalize an answer.
    Read-only, no confirmation needed."""
    owner_id = (state or {}).get("user_id")
    memories = (
        await memory_service.retrieve_memories(owner_id, query, limit=min(max(limit, 1), 20))
        if query.strip() else
        await memory_service.list_memories_for_owner(owner_id, include_pending=False, limit=min(max(limit, 1), 20))
    )
    if not memories:
        return "The user has no saved memories yet."
    lines = []
    for memory in memories:
        category = guardrail_service.sanitize_untrusted_text(memory.category)
        title = guardrail_service.sanitize_untrusted_text(memory.title)
        detail = guardrail_service.sanitize_untrusted_text(memory.detail or "")
        prefix = f"{memory.id} [{memory.memory_type}/{category}]" if query.strip() else f"[{category}]"
        lines.append(f"- {prefix} {title}: {detail}" if detail else f"- {prefix} {title}")
    return "\n".join(lines)


@tool
async def remember_fact(
    title: str,
    detail: str = "",
    memory_type: str = "fact",
    category: str = "Work",
    state: Annotated[AgentState, InjectedState] = None,  # type: ignore[assignment]
) -> str:
    """Save a durable user-scoped work memory only after explicit confirmation.

    Use only when the user explicitly asks Orbit to remember a preference, fact, entity,
    decision, open loop, or work knowledge. Never store passwords, tokens, private keys, medical
    details, or other sensitive inferred attributes.
    """
    allowed_types = {"preference", "fact", "entity", "decision", "open_loop", "knowledge"}
    if memory_type not in allowed_types:
        return "Loại memory không hợp lệ."
    content = f"{title}\n{detail}"
    if memory_service.is_forbidden_sensitive_memory(content):
        return "Orbit từ chối lưu thông tin xác thực hoặc thuộc tính cá nhân nhạy cảm vào memory."
    policy = guardrail_service.evaluate_action_content(content)
    if not policy.allowed:
        return policy.response

    draft = {"title": title, "detail": detail, "memory_type": memory_type, "category": category}
    decision = interrupt({"type": "memory_write", "draft": draft})
    if not decision or not decision.get("approved"):
        return "Memory was not saved (user declined)."
    draft.update(decision.get("edits") or {})
    content = f"{draft.get('title', '')}\n{draft.get('detail', '')}"
    if memory_service.is_forbidden_sensitive_memory(content):
        return "Orbit từ chối lưu thông tin xác thực hoặc thuộc tính cá nhân nhạy cảm vào memory."
    policy = guardrail_service.evaluate_action_content(content)
    if not policy.allowed:
        return policy.response

    owner_id = (state or {}).get("user_id")
    memory = Memory(
        owner_id=owner_id, workspace_id=(state or {}).get("workspace_id"),
        title=draft["title"], detail=draft.get("detail", ""),
        memory_type=draft.get("memory_type", memory_type), category=draft.get("category", category),
        status="active", source_type="user_confirmed", user_confirmed=True,
        source_thread_id=(state or {}).get("thread_id"),
        source_conversation_id=(state or {}).get("conversation_id"),
        provenance={"actor": "user", "channel": "agent_confirmation"}, confidence=1.0,
    )
    await memory_service.prepare_embedding(memory)
    async with db_session.async_session_maker() as db:
        duplicate = (
            await db.execute(
                select(Memory).where(
                    Memory.owner_id == owner_id, Memory.content_hash == memory.content_hash,
                    Memory.status.in_(["active", "pending_review"]),
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            return f"Memory đã tồn tại: {guardrail_service.sanitize_untrusted_text(duplicate.title)}."
        db.add(memory)
        await memory_service.supersede_exact_conflicts(db, memory)
        await db.commit()
    return f"Đã ghi nhớ: {guardrail_service.sanitize_untrusted_text(memory.title)}."


@tool
async def forget_memory(
    memory_id: str,
    state: Annotated[AgentState, InjectedState] = None,  # type: ignore[assignment]
) -> str:
    """Forget one saved memory by id. Call list_memories first if the id is unknown. Requires
    explicit confirmation and can only affect the current user's own memory."""
    owner_id = (state or {}).get("user_id")
    async with db_session.async_session_maker() as db:
        memory = (
            await db.execute(select(Memory).where(Memory.id == memory_id, Memory.owner_id == owner_id))
        ).scalar_one_or_none()
        if not memory:
            return "Không tìm thấy memory thuộc tài khoản này."
        draft = {"memory_id": memory.id, "title": memory.title}

    decision = interrupt({"type": "memory_delete", "draft": draft})
    if not decision or not decision.get("approved"):
        return "Memory was not forgotten (user declined)."
    async with db_session.async_session_maker() as db:
        memory = (
            await db.execute(select(Memory).where(Memory.id == memory_id, Memory.owner_id == owner_id))
        ).scalar_one_or_none()
        if not memory:
            return "Memory này không còn tồn tại."
        memory.status = "revoked"
        await db.commit()
    return f"Đã quên: {guardrail_service.sanitize_untrusted_text(draft['title'])}."
