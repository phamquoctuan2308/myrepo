from unittest.mock import AsyncMock, MagicMock

import pytest
from google.oauth2.credentials import Credentials
from sqlalchemy import select

import src.db.session as db_session
from src.auth.crypto import decrypt_secret
from src.auth.security import create_access_token
from src.db.models import GoogleCalendarCredential
from src.services import calendar_service, google_credentials
from src.websocket.manager import manager


async def _user_id(client, headers):
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


async def _credential(user_id: str) -> GoogleCalendarCredential | None:
    async with db_session.async_session_maker() as db:
        return (
            await db.execute(
                select(GoogleCalendarCredential).where(GoogleCalendarCredential.user_id == user_id)
            )
        ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_list_events_requires_auth(client):
    response = await client.get("/api/v1/calendar/events")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_events_returns_not_connected(client, auth_headers):
    response = await client.get("/api/v1/calendar/events", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "calendar_not_connected"


@pytest.mark.asyncio
async def test_list_events_uses_callers_calendar(client, auth_headers, monkeypatch):
    caller = await _user_id(client, auth_headers)
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt-1",
                "summary": "Team sync",
                "start": {"dateTime": "2026-08-10T10:00:00+07:00"},
                "end": {"dateTime": "2026-08-10T10:30:00+07:00"},
            }
        ]
    }

    async def fake_service(user_id):
        assert user_id == caller
        return service

    monkeypatch.setattr(calendar_service, "_service", fake_service)
    response = await client.get("/api/v1/calendar/events", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Team sync"
    assert service.events.return_value.list.call_args.kwargs["calendarId"] == "primary"


@pytest.mark.asyncio
async def test_create_event_uses_callers_calendar(client, auth_headers, monkeypatch):
    caller = await _user_id(client, auth_headers)
    service = MagicMock()

    def insert(calendarId=None, body=None):  # noqa: N803 - Google client kwarg
        assert calendarId == "primary"
        return MagicMock(
            execute=MagicMock(
                return_value={
                    "id": "evt-2",
                    "summary": body["summary"],
                    "start": body["start"],
                    "end": body["end"],
                }
            )
        )

    service.events.return_value.insert.side_effect = insert

    async def fake_service(user_id):
        assert user_id == caller
        return service

    monkeypatch.setattr(calendar_service, "_service", fake_service)
    response = await client.post(
        "/api/v1/calendar/events",
        json={
            "summary": "Design sync",
            "start_iso": "2026-08-11T09:00:00+07:00",
            "end_iso": "2026-08-11T09:30:00+07:00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["id"] == "evt-2"


@pytest.mark.asyncio
async def test_connection_status_and_oauth_state_are_user_bound(client, auth_headers):
    status_response = await client.get("/api/v1/calendar/connection", headers=auth_headers)
    assert status_response.json()["connected"] is False
    user_id = await _user_id(client, auth_headers)
    state = google_credentials.make_oauth_state(user_id)
    assert google_credentials.read_oauth_state(state) == user_id
    assert (
        await client.get(
            "/api/v1/calendar/oauth/callback", params={"code": "x", "state": create_access_token(user_id)}
        )
    ).status_code == 400


@pytest.mark.asyncio
async def test_oauth_callback_escapes_query_error_in_html_and_inline_script(client):
    attack = "</script><script>alert('xss')</script>"
    response = await client.get("/api/v1/calendar/oauth/callback", params={"error": attack})

    assert response.status_code == 400
    assert attack not in response.text
    assert "<script>alert" not in response.text
    assert "\\u003c/script\\u003e" in response.text


@pytest.mark.asyncio
async def test_calendar_errors_do_not_expose_upstream_exception(client, auth_headers, monkeypatch):
    async def broken_list(*_args, **_kwargs):
        raise RuntimeError("secret provider detail")

    monkeypatch.setattr(calendar_service, "list_events", broken_list)
    response = await client.get("/api/v1/calendar/events", headers=auth_headers)
    assert response.status_code == 502
    assert response.json()["detail"] == "Google Calendar is temporarily unavailable"
    assert "secret provider detail" not in response.text


@pytest.mark.asyncio
async def test_refresh_token_is_encrypted_at_rest(client, auth_headers):
    user_id = await _user_id(client, auth_headers)
    plaintext = "1//secret-refresh-token"
    credentials = Credentials(token="access", refresh_token=plaintext, scopes=google_credentials.SCOPES)
    await google_credentials.save_credentials(user_id, credentials, google_email="alice@example.com")
    row = await _credential(user_id)
    assert row is not None
    assert plaintext not in row.refresh_token_enc
    assert decrypt_secret(row.refresh_token_enc) == plaintext


@pytest.mark.asyncio
async def test_disconnect_removes_credential(client, auth_headers, monkeypatch):
    user_id = await _user_id(client, auth_headers)
    credentials = Credentials(token="access", refresh_token="refresh", scopes=google_credentials.SCOPES)
    await google_credentials.save_credentials(user_id, credentials)
    monkeypatch.setattr("httpx.AsyncClient.post", AsyncMock())
    response = await client.delete("/api/v1/calendar/connection", headers=auth_headers)
    assert response.status_code == 204
    assert await _credential(user_id) is None


@pytest.mark.asyncio
async def test_broadcast_reaches_only_calendar_owner(monkeypatch):
    broadcast = AsyncMock()
    monkeypatch.setattr(manager, "broadcast_to_users", broadcast)
    await calendar_service.broadcast_change("owner", "calendar_event_created", {"event": {"id": "e1"}})
    broadcast.assert_awaited_once_with(
        ["owner"], {"type": "calendar_event_created", "event": {"id": "e1"}}
    )


@pytest.mark.asyncio
async def test_poll_only_checks_online_connected_users(monkeypatch):
    monkeypatch.setattr(google_credentials, "list_connected_user_ids", AsyncMock(return_value=["online", "offline"]))
    poll = AsyncMock()
    monkeypatch.setattr(calendar_service, "_poll_one_user", poll)
    manager.active["online"] = {object()}
    try:
        await calendar_service.poll_calendar_changes()
    finally:
        manager.active.pop("online", None)
    poll.assert_awaited_once_with("online")
