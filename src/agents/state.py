from __future__ import annotations

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """State schema cho LangGraph agent.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.
    """

    query: str
    context: str
    analysis: str
    response: str
    error: str
    metadata: dict
    guardrail_blocked: bool
    guardrail_requires_clarification: bool
    user_id: str | None  # id of the user driving this run, for tools that push WS updates to them
    workspace_id: str | None  # active workspace for tenant-scoped tools
    conversation_id: str | None
    consent_scope_hash: str | None
    source_message_ids: list[str]
    thread_summary: str
    thread_id: str | None
    user_context: dict
    memory_context: str
    episodic_context: str
    conversation_summary_context: str
    prompt_messages: list[AnyMessage]
    context_metadata: dict

    # Tool-calling planner loop (messages, ToolNode, tools_condition all require this).
    messages: Annotated[list[AnyMessage], add_messages]

    # Structured outputs of the summarize/calendar/reminder tools.
    summary: str
    calendar_event_draft: dict | None
    reminder_draft: dict | None

    # Guardrail (input_guardrail_node/output_guardrail_node in guardrail_node.py) - a blocked or
    # clarification-needed request ends the run right after input_guardrail without reaching the
    # planner, so no tokens are spent and no tool ever sees a rejected request.
    guardrail_blocked: bool
    guardrail_requires_clarification: bool

    # context_node.py's output: a token-budgeted view of recent turns (prompt_messages) plus a
    # rendered summary of the user's saved Memory notes (memory_context) - planner_node.py prefers
    # these over the raw `messages`/no-memory system prompt when context_node has run, and falls
    # back to the old behavior otherwise so a run that skips context_node (e.g. a test that calls
    # planner_node directly) still works unchanged.
    memory_context: str
    episodic_context: str  # rendered MemoryEpisode summaries (memory_maintenance_service.py)
    prompt_messages: list
    context_metadata: dict
