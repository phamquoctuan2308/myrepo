from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.main import app
from src.websocket.manager import ConnectionManager


@pytest.fixture
def ws_client(client, monkeypatch):
    """Sync TestClient sharing the async `client` fixture's in-memory DB.

    Websockets need Starlette's sync TestClient (httpx's AsyncClient/ASGITransport doesn't
    support them). Entering it as a context manager fires app lifespan, so `init_db()` is
    stubbed out here - the schema already exists via the session-scoped `_test_database`
    fixture, and re-running `create_all` is harmless but pointless. Same reasoning for
    `scheduler.start()`/`.shutdown()` (would touch the real `apscheduler_jobs` table for no
    reason) and `init_checkpointer()`/`close_checkpointer()` (the checkpointer pool is already
    open for the whole test session via `_test_database` - calling `init_checkpointer()` again
    here would open a second pool and rebind the shared `agent` to it, then `close_checkpointer()`
    would close that pool on exit and break every `/chat` test that runs afterwards).
    """

    async def _noop():
        return None

    monkeypatch.setattr("src.main.init_db", _noop)
    monkeypatch.setattr("src.main.init_checkpointer", _noop)
    monkeypatch.setattr("src.main.close_checkpointer", _noop)
    monkeypatch.setattr("src.main.scheduler.start", lambda *a, **k: None)
    monkeypatch.setattr("src.main.scheduler.shutdown", lambda *a, **k: None)
    with TestClient(app) as tc:
        yield tc


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(ws_client):
    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect("/api/v1/ws?ticket=not-a-real-ticket"):
            pass


@pytest.mark.asyncio
async def test_websocket_send_broadcasts_to_participant(client, auth_headers, other_auth_headers, ws_client):
    alice = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
    bob = (await client.get("/api/v1/auth/me", headers=other_auth_headers)).json()
    alice_ticket = (await client.post("/api/v1/auth/ws-ticket", headers=auth_headers)).json()["ticket"]
    bob_ticket = (await client.post("/api/v1/auth/ws-ticket", headers=other_auth_headers)).json()["ticket"]
    workspace = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Realtime Team"},
            headers=auth_headers,
        )
    ).json()
    member_response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": bob["email"], "role": "member"},
        headers=auth_headers,
    )
    assert member_response.status_code == 201

    conv = (
        await client.post(
            "/api/v1/conversations",
            json={
                "type": "direct",
                "participant_ids": [bob["id"]],
                "workspace_id": workspace["id"],
            },
            headers=auth_headers,
        )
    ).json()

    with ws_client.websocket_connect(f"/api/v1/ws?ticket={alice_ticket}") as alice_ws:
        with ws_client.websocket_connect(f"/api/v1/ws?ticket={bob_ticket}") as bob_ws:
            alice_ws.send_json({"type": "send_message", "conversation_id": conv["id"], "content": "hi bob"})
            received = bob_ws.receive_json()
            assert received["type"] == "new_message"
            assert received["message"]["content"] == "hi bob"
            assert received["message"]["sender_id"] == alice["id"]

    history = await client.get(f"/api/v1/conversations/{conv['id']}/messages", headers=auth_headers)
    assert any(m["content"] == "hi bob" for m in history.json()["messages"])


@pytest.mark.asyncio
async def test_broadcast_removes_dead_socket_without_skipping_healthy_socket():
    connection_manager = ConnectionManager()
    dead = AsyncMock()
    dead.send_json.side_effect = RuntimeError("closed")
    healthy = AsyncMock()
    connection_manager.active["user-1"] = {dead, healthy}

    await connection_manager.broadcast_to_users(["user-1"], {"type": "ping"})

    healthy.send_json.assert_awaited_once_with({"type": "ping"})
    assert connection_manager.active["user-1"] == {healthy}


@pytest.mark.asyncio
async def test_disconnect_user_closes_and_removes_all_sockets():
    connection_manager = ConnectionManager()
    first = AsyncMock()
    second = AsyncMock()
    connection_manager.active["user-1"] = {first, second}

    await connection_manager.disconnect_user("user-1")

    assert "user-1" not in connection_manager.active
    first.close.assert_awaited_once_with(code=4003)
    second.close.assert_awaited_once_with(code=4003)
