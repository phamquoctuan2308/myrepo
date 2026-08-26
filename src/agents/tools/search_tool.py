from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.agents.state import AgentState
from src.db import session as db_session
from src.services import consent_service, guardrail_service


@tool
async def search_messages(
    query: str,
    max_results: int = 20,
    state: Annotated[AgentState, InjectedState] = None,  # type: ignore[assignment]
) -> str:
    """Search consent-authorized messages in the active conversation.

    Use this read-only tool when the user refers to an older message, decision, date, name, or link
    that is not present in the immediate context. The conversation identity is injected by the
    server and cannot be supplied or changed by the model.
    """
    conversation_id = (state or {}).get("conversation_id")
    if not conversation_id:
        return "No active conversation history is available to search."
    async with db_session.async_session_maker() as db:
        result = await consent_service.search_authorized_messages(
            db, conversation_id, query, max_results
        )
    if not result:
        return f"No authorized messages matched '{query}'."
    return guardrail_service.sanitize_untrusted_text(result)
