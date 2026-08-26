from unittest.mock import AsyncMock

import pytest

from src.agents.tools import task_tool


@pytest.mark.asyncio
async def test_extract_tasks_reads_context_from_state(monkeypatch):
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(
        content='[{"title": "Send report", "due_at": null, "priority": "High"}]', usage_metadata=None
    )
    monkeypatch.setattr(task_tool, "get_llm", lambda: fake_llm)

    state = {"context": "Alice: don't forget to send the report Friday"}
    result = await task_tool.extract_tasks.coroutine(state=state)

    assert result == '[{"title":"Send report","due_at":null,"priority":"High"}]'
    fake_llm.ainvoke.assert_awaited_once()
    prompt = fake_llm.ainvoke.await_args.args[0]
    assert "send the report" in prompt
    assert "JSON array" in prompt


@pytest.mark.asyncio
async def test_extract_tasks_no_context(monkeypatch):
    fake_llm = AsyncMock()
    monkeypatch.setattr(task_tool, "get_llm", lambda: fake_llm)

    result = await task_tool.extract_tasks.coroutine(state={})

    assert result == "[]"
    fake_llm.ainvoke.assert_not_awaited()


def test_state_hidden_from_llm_tool_schema():
    assert list(task_tool.extract_tasks.args.keys()) == []


# NOTE: task_tool.list_tasks (feature/delivery-agent-tools' read-only "list saved tasks" tool) was
# dropped when this test suite was ported onto develop - src.agents.tools.context_tool.list_my_tasks
# is develop's own equivalent, already wired into ALL_TOOLS.


@pytest.mark.asyncio
async def test_generate_tasks_json_logs_usage(monkeypatch):
    """★ fix: generate_tasks_json tự gọi LLM riêng nhưng trước đây không log usage - budget
    tracking tính thiếu lượt này. Xác nhận log_usage được gọi đúng với usage_metadata thật."""
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(
        content="[]", usage_metadata={"input_tokens": 8, "output_tokens": 2, "total_tokens": 10}
    )
    monkeypatch.setattr(task_tool, "get_llm", lambda: fake_llm)

    logged = {}

    async def fake_log_usage(**kwargs):
        logged.update(kwargs)

    monkeypatch.setattr(task_tool.usage_service, "log_usage", fake_log_usage)

    result = await task_tool.generate_tasks_json("Alice: hi")

    assert result == "[]"
    assert logged["usage_metadata"]["total_tokens"] == 10


@pytest.mark.asyncio
async def test_task_prompt_excludes_preferences_roles_and_completed_work(monkeypatch):
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(content="[]", usage_metadata=None)
    monkeypatch.setattr(task_tool, "get_llm", lambda: fake_llm)

    await task_tool.generate_tasks_json("Lan owns backend. Redis was completed.")

    prompt = fake_llm.ainvoke.await_args.args[0]
    assert "general roles/responsibilities" in prompt
    assert "completed or cancelled work" in prompt
    assert "conditional social suggestions" in prompt
    assert "Never turn remembered personal facts into tasks" in prompt
