"""Fast path for AIPanel's deterministic Quick Actions (Summarize, Extract tasks).

Both actions always send one fixed message that the planner's system prompt always maps to the
same one tool, every time (see planner_node.SYSTEM_PROMPT_TEMPLATE) - there's no real decision for
the planner to make here. routes.py calls run_quick_action() directly instead of running the
planner + LangGraph, cutting 2 LLM calls/click down to 1 (see ROADMAP.md, "batch LLM call").
"""

from typing import Literal

from src.agents.tools.summarize_tool import generate_summary
from src.agents.tools.task_tool import generate_tasks_json

QuickAction = Literal["summarize", "extract_tasks"]


async def run_quick_action(
    quick_action: QuickAction, context: str, *, user_id: str | None = None, workspace_id: str | None = None
) -> str:
    """Generate the result for one deterministic quick action directly - exactly one LLM call,
    no planner pass."""
    if quick_action == "summarize":
        return await generate_summary(context, user_id=user_id, workspace_id=workspace_id)
    if quick_action == "extract_tasks":
        return await generate_tasks_json(context, user_id=user_id, workspace_id=workspace_id)
    raise ValueError(f"Unknown quick_action: {quick_action!r}")  # unreachable - Pydantic already validates the schema
