from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages

from src.agents.state import AgentState
from src.config import get_settings
from src.services import conversation_summary_service, guardrail_service, memory_service


def _last_user_text(state: AgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return message.content
    return state.get("query", "")


def _fit(text: str, token_budget: int) -> str:
    # Conservative provider-independent approximation; count_tokens_approximately is used for
    # message objects below. Never split beyond the budget just because a retrieval source is big.
    char_budget = max(0, token_budget * 4)
    if len(text) <= char_budget:
        return text
    return text[:char_budget].rsplit("\n", 1)[0] + "\n[context trimmed]"


def budgeted_messages(state: AgentState):
    settings = get_settings()
    max_tokens = max(512, int(settings.agent_context_window_tokens * settings.memory_short_term_fraction))
    return trim_messages(
        state.get("messages", []),
        max_tokens=max_tokens,
        token_counter=count_tokens_approximately,
        strategy="last",
        include_system=False,
        allow_partial=False,
    )


async def context_node(state: AgentState) -> dict:
    """Build the optional context layers; policy/system context is assembled later and protected."""
    settings = get_settings()
    query = _last_user_text(state)
    owner_id = state.get("user_id")
    memories, episodes = await memory_service.retrieve_memories(owner_id, query), await memory_service.retrieve_episodes(
        owner_id, query
    )

    memory_lines = []
    for memory in memories:
        line = f"[{memory.memory_type}/{memory.category}] {memory.title}"
        if memory.detail:
            line += f": {memory.detail}"
        memory_lines.append(guardrail_service.sanitize_untrusted_text(line))

    episode_lines = []
    for episode in episodes:
        line = episode.summary
        if episode.decisions:
            line += " | decisions: " + "; ".join(map(str, episode.decisions))
        if episode.open_loops:
            line += " | open loops: " + "; ".join(map(str, episode.open_loops))
        episode_lines.append(guardrail_service.sanitize_untrusted_text(line))

    long_budget = int(settings.agent_context_window_tokens * settings.memory_long_term_fraction)
    episode_budget = int(settings.agent_context_window_tokens * settings.memory_episodic_fraction)
    retrieval_budget = int(settings.agent_context_window_tokens * settings.memory_retrieval_fraction)
    summary_budget = int(settings.agent_context_window_tokens * settings.memory_conversation_summary_fraction)

    conversation_id = state.get("conversation_id")
    rolling_summary = ""
    if conversation_id:
        # Consent-scoped rolling summary of this same Conversation's older history (see
        # conversation_summary_service.py) - distinct from memory_context/episodic_context, which
        # come from the user's cross-conversation Memory/MemoryEpisode store.
        rolling_summary = await conversation_summary_service.get_summary_text(conversation_id)

    return {
        "memory_context": _fit("\n".join(memory_lines), long_budget),
        "episodic_context": _fit("\n".join(episode_lines), episode_budget),
        "conversation_summary_context": _fit(rolling_summary, summary_budget),
        "context": _fit(state.get("context", ""), retrieval_budget),
        "prompt_messages": list(budgeted_messages(state)),
        "context_metadata": {
            "short_term_tokens": sum(count_tokens_approximately([m]) for m in budgeted_messages(state)),
            "long_term_memories": len(memories),
            "episodes": len(episodes),
            "conversation_context": bool(state.get("context", "").strip()),
            "rolling_summary_present": bool(rolling_summary.strip()),
        },
    }
