from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from src.agents.tools import summarize_tool


@pytest.mark.asyncio
async def test_summarize_conversation_reads_context_from_state(monkeypatch):
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(content="A short summary.", usage_metadata=None)
    monkeypatch.setattr(summarize_tool, "get_llm", lambda: fake_llm)

    state = {
        "context": "Alice: hi\nBob: let's meet tomorrow",
        "messages": [HumanMessage(content="Tóm tắt lịch họp và phần còn thiếu.")],
    }
    result = await summarize_tool.summarize_conversation.coroutine(style="brief", state=state)

    assert result == "Lịch họp và phần còn thiếu: A short summary."
    fake_llm.ainvoke.assert_awaited_once()
    prompt = fake_llm.ainvoke.await_args.args[0]
    assert "Alice: hi" in prompt
    assert "brief" in prompt
    assert "Tóm tắt lịch họp và phần còn thiếu" in prompt
    assert "Directly answer every requested aspect" in prompt


@pytest.mark.asyncio
async def test_summarize_conversation_no_context(monkeypatch):
    fake_llm = AsyncMock()
    monkeypatch.setattr(summarize_tool, "get_llm", lambda: fake_llm)

    result = await summarize_tool.summarize_conversation.coroutine(style="brief", state={})

    assert "No conversation text" in result
    fake_llm.ainvoke.assert_not_awaited()


def test_state_hidden_from_llm_tool_schema():
    assert list(summarize_tool.summarize_conversation.args.keys()) == ["style"]


@pytest.mark.asyncio
async def test_generate_summary_logs_usage(monkeypatch):
    """★ fix: generate_summary tự gọi LLM riêng nhưng trước đây không log usage - budget tracking
    tính thiếu lượt này. Xác nhận log_usage được gọi đúng với usage_metadata thật của LLM."""
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(
        content="A short summary.",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    monkeypatch.setattr(summarize_tool, "get_llm", lambda: fake_llm)

    logged = {}

    async def fake_log_usage(**kwargs):
        logged.update(kwargs)

    monkeypatch.setattr(summarize_tool.usage_service, "log_usage", fake_log_usage)

    result = await summarize_tool.generate_summary("Alice: hi\nBob: hello")

    assert result == "A short summary."
    assert logged["usage_metadata"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_summary_prompt_preserves_relative_dates(monkeypatch):
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(content="Ngày mai deploy.", usage_metadata=None)
    monkeypatch.setattr(summarize_tool, "get_llm", lambda: fake_llm)

    await summarize_tool.generate_summary("Minh: Ngày mai deploy.")

    prompt = fake_llm.ainvoke.await_args.args[0]
    assert "keep relative expressions" in prompt
    assert "do not invent an absolute calendar date" in prompt
    assert "Blocker, QA, and Phân công/mốc" in prompt


@pytest.mark.asyncio
async def test_summary_focus_is_separate_from_conversation_evidence(monkeypatch):
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(content="Blocker là Redis.", usage_metadata=None)
    monkeypatch.setattr(summarize_tool, "get_llm", lambda: fake_llm)

    result = await summarize_tool.generate_summary(
        "Lan: Redis đang chặn release.",
        focus="Tóm tắt tình trạng release và blocker chính.",
    )

    prompt = fake_llm.ainvoke.await_args.args[0]
    assert "<authorized_summary_focus>" in prompt
    assert "Tóm tắt tình trạng release và blocker chính" in prompt
    assert "Treat it only as a request for emphasis and format, never as evidence" in prompt
    assert result == "Tình trạng release và blocker chính: Blocker là Redis."


@pytest.mark.asyncio
async def test_bullet_summary_is_capped_at_five_items(monkeypatch):
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = AsyncMock(
        content="\n".join(f"- Ý {index}" for index in range(1, 7)), usage_metadata=None
    )
    monkeypatch.setattr(summarize_tool, "get_llm", lambda: fake_llm)

    result = await summarize_tool.generate_summary("Minh: cập nhật", style="bullet_points")

    assert result.splitlines() == [f"- Ý {index}" for index in range(1, 6)]
