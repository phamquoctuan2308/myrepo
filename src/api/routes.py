import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents import graph as agent_graph
from src.auth.dependencies import get_current_user
from src.db.models import Conversation, User, Workspace
from src.db.session import get_db
from src.models.schemas import (
    AuthorizedContextMetadata,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    InterruptPayload,
    ResumeRequest,
)
from src.models.usage_schemas import UsageStatusOut
from src.services import (
    assistant_thread_service,
    chat_service,
    consent_service,
    guardrail_service,
    quick_action_service,
    thread_memory_service,
    usage_service,
)
from src.services.authorization_service import require_conversation_access
from src.services.workspace_service import resolve_workspace_for_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _format_messages(messages: list[ChatMessage]) -> str:
    return "\n".join(f"{m.sender or m.role}: {m.content}" for m in messages)


def _build_chat_response(
    result: dict,
    thread_id: str,
    context_scope: AuthorizedContextMetadata | None = None,
) -> ChatResponse:
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        return ChatResponse(
            response="Please confirm the proposed action.",
            thread_id=thread_id,
            status="interrupted",
            interrupt=InterruptPayload(**payload),
            context_scope=context_scope,
        )

    error = result.get("error")
    if error:
        return ChatResponse(response=error, thread_id=thread_id, status="error", context_scope=context_scope)

    final_text = ""
    for m in reversed(result.get("messages", [])):
        # A trailing ToolMessage means graph.py routed straight to END after a "terminal" tool
        # (summarize_conversation/extract_tasks) - its content is already the final answer.
        if isinstance(m, (AIMessage, ToolMessage)) and m.content:
            final_text = m.content
            break
    if not final_text:
        final_text = (
            "Orbit không tạo được câu trả lời cho yêu cầu này — hãy thử diễn đạt lại hoặc hỏi cụ "
            "thể hơn."
        )
    return ChatResponse(
        response=final_text,
        thread_id=thread_id,
        status="completed",
        context_scope=context_scope,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Chat với AI agent."""
    thread_id = request.thread_id or str(uuid4())

    # Ràng buộc đề bài: "tối ưu chi phí" - chặn hẳn cuộc gọi LLM mới (không chỉ cảnh báo) một khi
    # đã chạm daily_token_budget. Chỉ áp dụng cho lượt chat MỚI - resume_chat() bên dưới cố tình
    # không chặn, vì nó hoàn tất một hành động con người đã bấm xác nhận rồi (human-in-the-loop),
    # chặn ở đó sẽ để interrupt() treo lơ lửng không cách nào hoàn tất hay huỷ.
    if await usage_service.is_over_budget():
        return ChatResponse(
            response=(
                "Đã vượt hạn mức token/chi phí AI hôm nay. Vui lòng thử lại vào ngày mai hoặc "
                "liên hệ admin để tăng hạn mức."
            ),
            thread_id=thread_id,
            status="error",
        )

    if request.conversation_id is not None:
        await require_conversation_access(db, current_user, request.conversation_id, "viewer")
        conversation = await db.get(Conversation, request.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        if request.workspace_id is not None and request.workspace_id != conversation.workspace_id:
            # For an `organization`-anchored conversation this really is a client-state bug worth
            # rejecting. For a `personal`-anchored one it's expected and harmless: a direct/group
            # conversation between two personal-workspace users is stored under whichever side's
            # personal workspace created it first (see chat_service.get_or_create_direct_conversation),
            # but the OTHER participant's own default `workspace_id` (WorkspaceContext, sent on
            # every /chat call) is their own, different, personal workspace - not the
            # conversation's anchor. `require_conversation_access` above already fully authorizes
            # this request via the real ConversationParticipant row, and `workspace_id` below is
            # always taken from the conversation regardless of what the client sent, so the mismatch
            # carries no security meaning here.
            anchor_workspace = await db.get(Workspace, conversation.workspace_id)
            if anchor_workspace is not None and anchor_workspace.type == "organization":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="conversation_id does not belong to workspace_id",
                )
        workspace_id = conversation.workspace_id
    else:
        workspace = await resolve_workspace_for_user(db, current_user.id, request.workspace_id)
        workspace_id = workspace.id
    if request.conversation_id is not None:
        # Conversation membership and AI consent are separate checks.
        await chat_service.assert_ai_permission(db, request.conversation_id, current_user.id)

    internal_thread_id, expired = await thread_memory_service.prepare_thread(
        db, current_user, workspace_id, thread_id
    )
    if expired:
        await agent_graph.checkpointer.adelete_thread(internal_thread_id)
    config = {"configurable": {"thread_id": internal_thread_id}}
    context_scope = None
    conversation_view = None
    if request.conversation_id is not None:
        conversation_view = await consent_service.build_authorized_message_view(
            db,
            request.conversation_id,
            request.context_limit,
            user_id=current_user.id,
            scope=request.scope,
        )
        context_text = conversation_view.text
        context_scope = AuthorizedContextMetadata(
            included_participants=conversation_view.included_participant_names,
            excluded_participants=conversation_view.excluded_participant_names,
            included_message_count=conversation_view.included_message_count,
            window_message_count=conversation_view.window_message_count,
            coverage=conversation_view.coverage,
            source_message_ids=conversation_view.source_message_ids,
            consent_scope_hash=conversation_view.consent_scope_hash,
        )
        if conversation_view.window_message_count and not conversation_view.source_message_ids:
            return ChatResponse(
                response="Không có tin nhắn nào trong phạm vi đã chọn được phép xử lý bởi Assistant.",
                thread_id=thread_id,
                status="completed",
                context_scope=context_scope,
            )
    else:
        scoped_messages = request.messages[-request.context_limit :] if request.messages else []
        context_text = _format_messages(scoped_messages)

    if request.quick_action:
        # AIPanel's deterministic Quick Actions (Summarize/Extract tasks) always send one fixed
        # message the planner's system prompt always maps to the same tool - there's no real
        # decision to make, so the planner's LLM call is pure overhead. Skip the planner + the
        # whole LangGraph/checkpointer run entirely and call the tool's own logic directly - 1 LLM
        # call instead of 2. Runs after the conversation access/consent/budget checks above, so it
        # gets the same guarantees as the graph path, just no LLM decision step after them.
        request_decision = guardrail_service.evaluate_request(
            request.message, conversation_mode=bool(request.conversation_id)
        )
        context_decision = guardrail_service.evaluate_context(context_text)
        blocked = request_decision if not request_decision.allowed else context_decision
        if not blocked.allowed:
            return ChatResponse(
                response=blocked.response, thread_id=thread_id, status="completed", context_scope=context_scope
            )
        try:
            text = await quick_action_service.run_quick_action(
                request.quick_action, context_text, user_id=current_user.id, workspace_id=workspace_id
            )
        except Exception:
            logger.exception("Quick action failed")
            raise HTTPException(status_code=500, detail="The AI quick action failed") from None
        output_decision = guardrail_service.evaluate_output(text)
        if not output_decision.allowed:
            text = output_decision.response
        return ChatResponse(response=text, thread_id=thread_id, status="completed", context_scope=context_scope)

    inputs = {
        "messages": [HumanMessage(content=request.message)],
        # Preserve the original data so the deterministic guard can classify it accurately.
        # Each LLM-facing consumer sanitizes it at its own trust boundary.
        "context": context_text,
        "user_id": current_user.id,
        "workspace_id": workspace_id,
        "conversation_id": request.conversation_id,
        "thread_id": thread_id,
        "consent_scope_hash": conversation_view.consent_scope_hash if conversation_view else None,
        "source_message_ids": conversation_view.source_message_ids if conversation_view else [],
        "user_context": {
            "display_name": current_user.display_name,
            "job_title": current_user.job_title,
            "timezone": current_user.timezone,
            "preferences": current_user.preferences,
        },
    }
    try:
        result = await agent_graph.agent.ainvoke(inputs, config)
    except Exception:
        raise HTTPException(status_code=500, detail="AI service is temporarily unavailable")
    response = _build_chat_response(result, thread_id, context_scope)
    if request.conversation_id is None and response.status != "error":
        preview = response.response if response.status == "completed" else request.message
        await assistant_thread_service.touch_new_or_existing(
            db,
            thread_id=thread_id,
            owner_id=current_user.id,
            user_message=request.message,
            ai_preview=preview,
        )
    return response


@router.post("/chat/resume", response_model=ChatResponse)
async def resume_chat(
    request: ResumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Resume an interrupted agent run with the user's confirm/reject decision."""
    thread = await thread_memory_service.require_resumable_thread(
        db, current_user, request.thread_id
    )
    config = {"configurable": {"thread_id": thread.id}}
    try:
        snapshot = await agent_graph.agent.aget_state(config)
        state_values = snapshot.values or {}
        conversation_id = state_values.get("conversation_id")
        consent_scope_hash = state_values.get("consent_scope_hash")
        if conversation_id:
            await chat_service.assert_ai_permission(db, conversation_id, current_user.id)
            current_hash = await consent_service.get_consent_scope_hash(db, conversation_id)
            if not consent_scope_hash or current_hash != consent_scope_hash:
                return ChatResponse(
                    response=(
                        "Quyền AI của conversation đã thay đổi từ khi hành động được đề xuất. "
                        "Vui lòng mở lại conversation và tạo đề xuất mới."
                    ),
                    thread_id=request.thread_id,
                    status="error",
                )
        result = await agent_graph.agent.ainvoke(
            Command(resume={"approved": request.approved, "edits": request.edits}), config
        )
    except Exception:
        raise HTTPException(status_code=500, detail="AI service is temporarily unavailable")
    response = _build_chat_response(result, request.thread_id)
    if response.status != "error":
        preview = response.response if response.status == "completed" else "Đang chờ xác nhận thêm..."
        await assistant_thread_service.touch_if_exists(
            db,
            owner_id=current_user.id,
            thread_id=request.thread_id,
            ai_preview=preview,
        )
    return response


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}


@router.get("/usage/status", response_model=UsageStatusOut)
async def usage_status(current_user: User = Depends(get_current_user)) -> UsageStatusOut:
    del current_user
    return UsageStatusOut(**(await usage_service.get_usage_summary()))
