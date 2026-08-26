from src.agents.tools.calendar_tool import (
    create_calendar_event,
    delete_calendar_event,
    list_calendar_events,
    update_calendar_event,
)
from src.agents.tools.context_tool import get_personal_timeline, list_my_tasks, search_my_memories
from src.agents.tools.memory_tool import forget_memory, list_memories, remember_fact
from src.agents.tools.policy_tool import check_request_policy
from src.agents.tools.reminder_tool import create_reminder, list_reminders
from src.agents.tools.search_tool import search_messages
from src.agents.tools.summarize_tool import summarize_conversation
from src.agents.tools.task_tool import extract_tasks

# example_tool.py's search_knowledge/calculate are left as unwired reference examples,
# not part of the production tool set.
ALL_TOOLS = [
    check_request_policy,
    summarize_conversation,
    extract_tasks,
    create_calendar_event,
    list_calendar_events,
    update_calendar_event,
    delete_calendar_event,
    create_reminder,
    list_reminders,
    list_my_tasks,
    search_my_memories,
    list_memories,
    remember_fact,
    forget_memory,
    search_messages,
    get_personal_timeline,
]

__all__ = [
    "ALL_TOOLS",
    "check_request_policy",
    "summarize_conversation",
    "extract_tasks",
    "create_calendar_event",
    "list_calendar_events",
    "update_calendar_event",
    "delete_calendar_event",
    "create_reminder",
    "list_reminders",
    "list_my_tasks",
    "search_my_memories",
    "list_memories",
    "remember_fact",
    "forget_memory",
    "search_messages",
    "get_personal_timeline",
]
