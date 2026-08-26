from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents.nodes import context_node
from src.db import session as db_session
from src.db.models import ConversationRollingSummary
from src.services import conversation_summary_service


@pytest.fixture(autouse=True)
def _disable_route_background_tasks(monkeypatch):
    """Sending a message must not run the real proactive/event workers during these tests."""
    monkeypatch.setattr(
        "starlette.background.BackgroundTasks.add_task",
        lambda self, func, *args, **kwargs: None,
    )


def _settings(
    *,
    enabled: bool = True,
    threshold: int = 2,
    batch_size: int = 60,
    max_chars: int = 12_000,
    sweep_limit: int = 10,
) -> SimpleNamespace:
    return SimpleNamespace(
        conversation_summary_enabled=enabled,
        conversation_summary_threshold_messages=threshold,
        conversation_summary_batch_size=batch_size,
        conversation_summary_max_chars=max_chars,
        conversation_summary_sweep_limit=sweep_limit,
        llm_provider="google",
        model_name="gemini-test",
    )


def _fake_llm(*summaries: str) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke.side_effect = [
        SimpleNamespace(content=f'{{"summary": "{text}"}}', usage_metadata={}) for text in summaries
    ]
    return llm


async def _create_direct_conversation(client, creator_headers, other_headers):
    creator = (await client.get("/api/v1/auth/me", headers=creator_headers)).json()
    other = (await client.get("/api/v1/auth/me", headers=other_headers)).json()
    workspace = (
        await client.post(
            "/api/v1/workspaces", json={"name": "Rolling summary test team"}, headers=creator_headers
        )
    ).json()
    add_member = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": other["email"], "role": "member"},
        headers=creator_headers,
    )
    assert add_member.status_code == 201
    response = await client.post(
        "/api/v1/conversations",
        json={"type": "direct", "participant_ids": [other["id"]], "workspace_id": workspace["id"]},
        headers=creator_headers,
    )
    assert response.status_code == 200
    return response.json()["id"], creator, other


async def _grant_ai(client, conversation_id, headers, *, granted=True, contribution_allowed=True):
    response = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission",
        json={"granted": granted, "contribution_allowed": contribution_allowed},
        headers=headers,
    )
    assert response.status_code == 200


async def _send(client, conversation_id, headers, content: str) -> dict:
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": content}, headers=headers
    )
    assert response.status_code == 200
    return response.json()


async def _get_row(conversation_id: str) -> ConversationRollingSummary | None:
    async with db_session.async_session_maker() as db:
        return await db.get(ConversationRollingSummary, conversation_id)


@pytest.mark.asyncio
async def test_only_consenting_sender_messages_are_folded_into_summary(
    client, auth_headers, other_auth_headers, monkeypatch
):
    conversation_id, creator, _other = await _create_direct_conversation(
        client, auth_headers, other_auth_headers
    )
    # Only the creator grants contribution consent - the other participant never does.
    await _grant_ai(client, conversation_id, auth_headers)
    await _send(client, conversation_id, auth_headers, "Tin nhắn được phép số 1")
    await _send(client, conversation_id, auth_headers, "Tin nhắn được phép số 2")
    await _send(client, conversation_id, other_auth_headers, "Nội dung không được phép đọc")

    llm = _fake_llm("Tóm tắt ban đầu")
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm)
    monkeypatch.setattr(conversation_summary_service, "get_settings", lambda: _settings(threshold=2))

    changed = await conversation_summary_service._consolidate_conversation(conversation_id)

    assert changed is True
    prompt = llm.ainvoke.await_args.args[0]
    assert "được phép" in prompt
    assert "không được phép đọc" not in prompt
    row = await _get_row(conversation_id)
    assert row.summary == "Tóm tắt ban đầu"
    assert row.processed_message_count == 2


@pytest.mark.asyncio
async def test_revoking_contribution_flags_reset_and_rebuilds_summary(
    client, auth_headers, other_auth_headers, monkeypatch
):
    conversation_id, creator, other = await _create_direct_conversation(
        client, auth_headers, other_auth_headers
    )
    await _grant_ai(client, conversation_id, auth_headers)
    await _grant_ai(client, conversation_id, other_auth_headers)
    await _send(client, conversation_id, auth_headers, "Trước khi thu hồi 1")
    await _send(client, conversation_id, other_auth_headers, "Trước khi thu hồi 2")

    llm = _fake_llm("Tóm tắt trước khi thu hồi")
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm)
    monkeypatch.setattr(conversation_summary_service, "get_settings", lambda: _settings(threshold=2))
    assert await conversation_summary_service._consolidate_conversation(conversation_id) is True
    row = await _get_row(conversation_id)
    assert row.summary == "Tóm tắt trước khi thu hồi"
    assert row.needs_reset is False

    revoke = await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission",
        json={"contribution_allowed": False},
        headers=other_auth_headers,
    )
    assert revoke.status_code == 200
    row = await _get_row(conversation_id)
    assert row.needs_reset is True

    await _send(client, conversation_id, auth_headers, "Sau khi thu hồi 1")
    await _send(client, conversation_id, auth_headers, "Sau khi thu hồi 2")
    llm2 = _fake_llm("Tóm tắt xây lại sau thu hồi")
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm2)
    assert await conversation_summary_service._consolidate_conversation(conversation_id) is True

    prompt = llm2.ainvoke.await_args.args[0]
    assert "no previous summary yet" in prompt  # reset wiped the previous summary before rebuilding
    # The rebuild replays every message from senders still eligible under the *current* consent
    # state, including creator's pre-revoke message (creator's own consent was never touched) -
    # only the revoked sender's content must be excluded.
    assert "Trước khi thu hồi 1" in prompt
    assert "Trước khi thu hồi 2" not in prompt
    row = await _get_row(conversation_id)
    assert row.summary == "Tóm tắt xây lại sau thu hồi"
    assert row.needs_reset is False
    assert row.processed_message_count == 3


@pytest.mark.asyncio
async def test_group_without_ai_enabled_never_creates_a_summary_row(
    client, auth_headers, other_auth_headers, monkeypatch
):
    other = (await client.get("/api/v1/auth/me", headers=other_auth_headers)).json()
    workspace = (
        await client.post("/api/v1/workspaces", json={"name": "Group summary team"}, headers=auth_headers)
    ).json()
    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": other["email"], "role": "member"},
        headers=auth_headers,
    )
    conversation = (
        await client.post(
            "/api/v1/conversations",
            json={
                "type": "group",
                "name": "Team chat",
                "participant_ids": [other["id"]],
                "workspace_id": workspace["id"],
            },
            headers=auth_headers,
        )
    ).json()
    conversation_id = conversation["id"]
    await _send(client, conversation_id, auth_headers, "Chưa bật AI cho nhóm này")

    llm = AsyncMock()
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm)
    monkeypatch.setattr(conversation_summary_service, "get_settings", lambda: _settings(threshold=1))

    changed = await conversation_summary_service._consolidate_conversation(conversation_id)

    assert changed is False
    llm.ainvoke.assert_not_awaited()
    assert await _get_row(conversation_id) is None


@pytest.mark.asyncio
async def test_below_threshold_is_a_noop(client, auth_headers, other_auth_headers, monkeypatch):
    conversation_id, *_ = await _create_direct_conversation(client, auth_headers, other_auth_headers)
    await _grant_ai(client, conversation_id, auth_headers)
    await _send(client, conversation_id, auth_headers, "Chỉ một tin nhắn thôi")

    llm = AsyncMock()
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm)
    monkeypatch.setattr(conversation_summary_service, "get_settings", lambda: _settings(threshold=5))

    changed = await conversation_summary_service._consolidate_conversation(conversation_id)

    assert changed is False
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_running_status_is_skipped_single_flight(
    client, auth_headers, other_auth_headers, monkeypatch
):
    conversation_id, *_ = await _create_direct_conversation(client, auth_headers, other_auth_headers)
    await _grant_ai(client, conversation_id, auth_headers)
    await _send(client, conversation_id, auth_headers, "Tin nhắn 1")
    await _send(client, conversation_id, auth_headers, "Tin nhắn 2")
    async with db_session.async_session_maker() as db:
        db.add(ConversationRollingSummary(conversation_id=conversation_id, status="running"))
        await db.commit()

    llm = AsyncMock()
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm)
    monkeypatch.setattr(conversation_summary_service, "get_settings", lambda: _settings(threshold=2))

    changed = await conversation_summary_service._consolidate_conversation(conversation_id)

    assert changed is False
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_over_budget_skips_llm_call_and_resets_status_to_idle(
    client, auth_headers, other_auth_headers, monkeypatch
):
    conversation_id, *_ = await _create_direct_conversation(client, auth_headers, other_auth_headers)
    await _grant_ai(client, conversation_id, auth_headers)
    await _send(client, conversation_id, auth_headers, "Tin nhắn 1")
    await _send(client, conversation_id, auth_headers, "Tin nhắn 2")

    llm = AsyncMock()
    monkeypatch.setattr(conversation_summary_service, "get_llm", lambda: llm)
    monkeypatch.setattr(conversation_summary_service, "get_settings", lambda: _settings(threshold=2))

    async def _over_budget():
        return True

    monkeypatch.setattr(conversation_summary_service.usage_service, "is_over_budget", _over_budget)

    changed = await conversation_summary_service._consolidate_conversation(conversation_id)

    assert changed is False
    llm.ainvoke.assert_not_awaited()
    row = await _get_row(conversation_id)
    assert row.status == "idle"


@pytest.mark.asyncio
async def test_context_node_injects_trimmed_rolling_summary(monkeypatch):
    settings = SimpleNamespace(
        agent_context_window_tokens=8_192,
        memory_short_term_fraction=0.10,
        memory_long_term_fraction=0.01,
        memory_episodic_fraction=0.0,
        memory_retrieval_fraction=0.0,
        memory_conversation_summary_fraction=0.01,
    )

    async def _no_memories(*_args, **_kwargs):
        return []

    async def _summary_text(conversation_id: str) -> str:
        assert conversation_id == "conv-123"
        return "r" * 5_000

    monkeypatch.setattr(context_node, "get_settings", lambda: settings)
    monkeypatch.setattr(context_node.memory_service, "retrieve_memories", _no_memories)
    monkeypatch.setattr(context_node.memory_service, "retrieve_episodes", _no_memories)
    monkeypatch.setattr(context_node.conversation_summary_service, "get_summary_text", _summary_text)

    result = await context_node.context_node({"user_id": "owner", "conversation_id": "conv-123"})

    budget_chars = int(8_192 * 0.01) * 4
    assert 0 < len(result["conversation_summary_context"]) <= budget_chars + len("\n[context trimmed]")
    assert result["context_metadata"]["rolling_summary_present"] is True
