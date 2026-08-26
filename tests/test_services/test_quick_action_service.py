import pytest

from src.services import quick_action_service


@pytest.mark.asyncio
async def test_run_quick_action_summarize_calls_generate_summary(monkeypatch):
    called = {}

    async def fake_generate_summary(context, *, user_id=None, workspace_id=None):
        called["context"] = context
        called["user_id"] = user_id
        called["workspace_id"] = workspace_id
        return "summary text"

    monkeypatch.setattr(quick_action_service, "generate_summary", fake_generate_summary)

    result = await quick_action_service.run_quick_action(
        "summarize", "ctx", user_id="user-1", workspace_id="workspace-1"
    )

    assert result == "summary text"
    assert called["context"] == "ctx"
    # Usage logging must be attributable to the caller, same as the full LangGraph tool path
    # (extract_tasks already passed these through - summarize previously silently dropped them).
    assert called["user_id"] == "user-1"
    assert called["workspace_id"] == "workspace-1"


@pytest.mark.asyncio
async def test_run_quick_action_extract_tasks_calls_generate_tasks_json(monkeypatch):
    called = {}

    async def fake_generate_tasks_json(context, *, user_id=None, workspace_id=None):
        called["context"] = context
        called["user_id"] = user_id
        called["workspace_id"] = workspace_id
        return "[]"

    monkeypatch.setattr(quick_action_service, "generate_tasks_json", fake_generate_tasks_json)

    result = await quick_action_service.run_quick_action(
        "extract_tasks", "ctx", user_id="user-1", workspace_id="workspace-1"
    )

    assert result == "[]"
    assert called["context"] == "ctx"
    assert called["user_id"] == "user-1"
    assert called["workspace_id"] == "workspace-1"
