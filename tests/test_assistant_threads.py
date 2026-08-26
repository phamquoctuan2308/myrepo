import pytest
from langchain_core.messages import AIMessage

from src.db import session as db_session
from src.services import assistant_thread_service


def _mock_reply(monkeypatch, fake_llm_factory, text: str):
    llm = fake_llm_factory([AIMessage(content=text)])
    monkeypatch.setattr("src.agents.nodes.planner_node.get_llm", lambda: llm)
    return llm


@pytest.mark.asyncio
async def test_fresh_chat_creates_assistant_thread(client, auth_headers, monkeypatch, fake_llm_factory):
    _mock_reply(monkeypatch, fake_llm_factory, "Đây là câu trả lời của Orbit.")

    resp = await client.post(
        "/api/v1/chat",
        json={"message": "  Tổng hợp lịch, task và deadline của tôi hôm nay  "},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    thread_id = resp.json()["thread_id"]

    listing = await client.get("/api/v1/assistant/threads", headers=auth_headers)
    assert listing.status_code == 200
    threads = listing.json()
    assert len(threads) == 1
    assert threads[0]["thread_id"] == thread_id
    assert threads[0]["title"] == "Tổng hợp lịch, task và deadline của tôi hôm nay"
    assert threads[0]["preview"] == "Đây là câu trả lời của Orbit."


@pytest.mark.asyncio
async def test_second_turn_updates_preview_not_title(client, auth_headers, monkeypatch, fake_llm_factory):
    _mock_reply(monkeypatch, fake_llm_factory, "Phản hồi lượt 1.")
    first = await client.post("/api/v1/chat", json={"message": "Tin nhắn đầu tiên"}, headers=auth_headers)
    thread_id = first.json()["thread_id"]

    _mock_reply(monkeypatch, fake_llm_factory, "Phản hồi lượt 2.")
    second = await client.post(
        "/api/v1/chat", json={"message": "Tin nhắn thứ hai", "thread_id": thread_id}, headers=auth_headers
    )
    assert second.status_code == 200

    listing = await client.get("/api/v1/assistant/threads", headers=auth_headers)
    threads = listing.json()
    assert len(threads) == 1
    assert threads[0]["title"] == "Tin nhắn đầu tiên"  # unchanged
    assert threads[0]["preview"] == "Phản hồi lượt 2."  # refreshed


@pytest.mark.asyncio
async def test_conversation_scoped_chat_does_not_create_assistant_thread(
    client, auth_headers, other_auth_headers, monkeypatch, fake_llm_factory
):
    """AIPanel's embedded quick actions/Ask Orbit always send conversation_id - those turns must
    not show up in the Personal Assistant's own "Gần đây" list."""
    _mock_reply(monkeypatch, fake_llm_factory, "Tóm tắt hội thoại.")
    other_me = await client.get("/api/v1/auth/me", headers=other_auth_headers)
    other = other_me.json()
    workspace = (
        await client.post(
            "/api/v1/workspaces", json={"name": "Assistant thread test"}, headers=auth_headers
        )
    ).json()
    await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": other["email"], "role": "member"},
        headers=auth_headers,
    )
    conv = await client.post(
        "/api/v1/conversations",
        json={
            "type": "direct",
            "participant_ids": [other["id"]],
            "workspace_id": workspace["id"],
        },
        headers=auth_headers,
    )
    conversation_id = conv.json()["id"]
    await client.put(
        f"/api/v1/conversations/{conversation_id}/ai-permission", json={"granted": True}, headers=auth_headers
    )

    resp = await client.post(
        "/api/v1/chat",
        json={"message": "Summarize this.", "conversation_id": conversation_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    listing = await client.get("/api/v1/assistant/threads", headers=auth_headers)
    assert listing.json() == []


@pytest.mark.asyncio
async def test_list_threads_only_returns_own(client, auth_headers, other_auth_headers, monkeypatch, fake_llm_factory):
    _mock_reply(monkeypatch, fake_llm_factory, "Reply for alice.")
    await client.post("/api/v1/chat", json={"message": "Alice's question"}, headers=auth_headers)

    _mock_reply(monkeypatch, fake_llm_factory, "Reply for bob.")
    await client.post("/api/v1/chat", json={"message": "Bob's question"}, headers=other_auth_headers)

    mine = (await client.get("/api/v1/assistant/threads", headers=auth_headers)).json()
    assert len(mine) == 1
    assert mine[0]["title"] == "Alice's question"


@pytest.mark.asyncio
async def test_thread_messages_returns_history_and_checks_ownership(
    client, auth_headers, other_auth_headers, monkeypatch, fake_llm_factory
):
    _mock_reply(monkeypatch, fake_llm_factory, "Câu trả lời thật.")
    resp = await client.post("/api/v1/chat", json={"message": "Câu hỏi thật"}, headers=auth_headers)
    thread_id = resp.json()["thread_id"]

    history = await client.get(f"/api/v1/assistant/threads/{thread_id}/messages", headers=auth_headers)
    assert history.status_code == 200
    messages = history.json()
    assert {"role": "user", "content": "Câu hỏi thật"} in messages
    assert {"role": "assistant", "content": "Câu trả lời thật."} in messages

    forbidden = await client.get(f"/api/v1/assistant/threads/{thread_id}/messages", headers=other_auth_headers)
    assert forbidden.status_code == 404

    missing = await client.get("/api/v1/assistant/threads/does-not-exist/messages", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_touch_if_exists_never_creates_a_row(client):
    """A resume for a conversation-embedded interrupt (thread never touched by a personal-assistant
    chat() call) must not retroactively create an AssistantThread row."""
    async with db_session.async_session_maker() as db:
        await assistant_thread_service.touch_if_exists(
            db, owner_id="whoever", thread_id="never-existed", ai_preview="irrelevant"
        )
        threads = await assistant_thread_service.list_threads(db, owner_id="whoever")
    assert threads == []
