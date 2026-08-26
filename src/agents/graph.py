from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg_pool import AsyncConnectionPool

from src.agents.nodes.compact_node import compact_thread_node
from src.agents.nodes.context_node import context_node
from src.agents.nodes.guardrail_node import input_guardrail_node, output_guardrail_node
from src.agents.nodes.planner_node import planner_node
from src.agents.state import AgentState
from src.agents.tools import ALL_TOOLS
from src.config import get_settings

# Tools whose own output is already the final answer - no confirmation needed and no benefit
# from a second LLM pass to "relay" it. Routing straight to END after these avoids that second
# pass, which some models handle poorly (observed: hallucinating a bogus repeat tool-call instead
# of plain text). Calendar/reminder tools still go back through planner - their raw output isn't
# user-facing prose, and human-in-the-loop confirmation flows need that turn.
TERMINAL_TOOLS = {"summarize_conversation", "extract_tasks"}


def route_after_planner(state: AgentState) -> str:
    """Route tool calls to execution and plain replies through output validation."""
    if state.get("error"):
        return END
    return "tools" if tools_condition(state) == "tools" else "output_guardrail"


def route_after_input_guardrail(state: AgentState) -> str:
    """A blocked request ends without spending tokens or exposing it to the planner."""
    return END if state.get("guardrail_blocked") or state.get("guardrail_requires_clarification") else "context_builder"


def route_after_tools(state: AgentState) -> str:
    """End immediately after a terminal tool (its output is the final answer); otherwise loop
    back to the planner so it can phrase a reply or decide on further tool calls."""
    last = state["messages"][-1]
    if isinstance(last, ToolMessage) and last.name in TERMINAL_TOOLS:
        return "output_guardrail"
    return "planner"


def build_graph(checkpointer):
    graph = StateGraph(AgentState)

    graph.add_node("input_guardrail", input_guardrail_node)
    graph.add_node("context_builder", context_node)
    graph.add_node("planner", planner_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_node("output_guardrail", output_guardrail_node)
    graph.add_node("compact_thread", compact_thread_node)

    graph.set_entry_point("input_guardrail")
    graph.add_conditional_edges(
        "input_guardrail", route_after_input_guardrail, {"context_builder": "context_builder", END: END}
    )
    graph.add_edge("context_builder", "planner")
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"tools": "tools", "output_guardrail": "output_guardrail", END: END},
    )
    graph.add_conditional_edges(
        "tools", route_after_tools, {"planner": "planner", "output_guardrail": "output_guardrail"}
    )
    graph.add_edge("output_guardrail", "compact_thread")
    graph.add_edge("compact_thread", END)

    return graph.compile(checkpointer=checkpointer)


_settings = get_settings()
_use_postgres = _settings.database_url.startswith(("postgresql://", "postgresql+asyncpg://", "postgres://"))

# `AsyncPostgresSaver` must be constructed inside a *running* event loop (it calls
# asyncio.get_running_loop() in __init__), which isn't available yet at module-import time -
# so it's built later, from init_checkpointer() during FastAPI's lifespan. `agent` stays None
# until then; no /chat call can succeed before init_checkpointer() has been awaited once.
#
# Lightweight development/tests (DATABASE_URL not Postgres - see tests/conftest.py) use MemorySaver
# instead: importing the graph then never requires a running event loop or an external database,
# and `agent` is ready immediately, no init_checkpointer() call needed.
if _use_postgres:
    checkpointer, checkpointer_pool, agent = None, None, None
else:
    checkpointer, checkpointer_pool = MemorySaver(), None
    agent = build_graph(checkpointer)


async def init_checkpointer() -> None:
    """Build the Postgres checkpointer/pool and compile `agent` with it. Must be awaited once,
    inside the event loop that will go on to serve requests, before any /chat call."""
    global checkpointer, checkpointer_pool, agent
    if not _use_postgres:
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    scheme, _, rest = _settings.database_url.partition("://")
    conninfo = f"{scheme.split('+')[0]}://{rest}"
    pool = AsyncConnectionPool(conninfo=conninfo, max_size=10, open=False, kwargs={"autocommit": True})
    await pool.open()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()

    checkpointer_pool = pool
    checkpointer = saver
    agent = build_graph(checkpointer)


async def close_checkpointer() -> None:
    if checkpointer_pool is not None:
        await checkpointer_pool.close()
