from datetime import datetime

import pytest

from src.services import reminder_service


@pytest.mark.asyncio
async def test_create_and_list_reminder(client, auth_headers):
    resp = await client.post(
        "/api/v1/reminders",
        json={"title": "Send report", "due_at_iso": "2099-08-10T15:00:00", "lead_minutes": 30},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Send report"
    assert body["status"] == "scheduled"
    assert body["source"] == "manual"

    resp = await client.get("/api/v1/reminders", headers=auth_headers)
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert "Send report" in titles


@pytest.mark.asyncio
async def test_reminders_require_auth(client):
    resp = await client.get("/api/v1/reminders")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_cancel_reminder(client, auth_headers):
    created = (
        await client.post(
            "/api/v1/reminders",
            json={"title": "Throwaway", "due_at_iso": "2099-08-10T15:00:00"},
            headers=auth_headers,
        )
    ).json()

    resp = await client.delete(f"/api/v1/reminders/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/reminders", headers=auth_headers)
    cancelled = next(r for r in resp.json() if r["id"] == created["id"])
    assert cancelled["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_missing_reminder_404(client, auth_headers):
    resp = await client.delete("/api/v1/reminders/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reminder_not_visible_to_other_user(client, auth_headers, other_auth_headers):
    created = (
        await client.post(
            "/api/v1/reminders",
            json={"title": "Private reminder", "due_at_iso": "2099-08-10T15:00:00"},
            headers=auth_headers,
        )
    ).json()

    resp = await client.get("/api/v1/reminders", headers=other_auth_headers)
    assert created["id"] not in [r["id"] for r in resp.json()]

    resp = await client.delete(f"/api/v1/reminders/{created['id']}", headers=other_auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------- realtime sync (ReminderPage.jsx)


@pytest.mark.asyncio
async def test_create_reminder_pushes_reminder_created(client, auth_headers, monkeypatch):
    """Regression test: every open tab's ReminderPage.jsx must see a new reminder without a
    manual reload, same as CalendarPage.jsx already gets for calendar_event_created."""
    pushed = []

    async def fake_broadcast(user_ids, payload):
        pushed.append((user_ids, payload))

    monkeypatch.setattr(reminder_service.manager, "broadcast_to_users", fake_broadcast)
    owner_id = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["id"]

    resp = await client.post(
        "/api/v1/reminders", json={"title": "Send report", "due_at_iso": "2099-08-10T15:00:00"}, headers=auth_headers
    )
    created = resp.json()

    assert len(pushed) == 1
    ids, payload = pushed[0]
    assert ids == [owner_id]
    assert payload["type"] == "reminder_created"
    # Same instant, not necessarily the same string - the REST response (Pydantic JSON mode)
    # renders UTC as "...Z" while the service's own dict uses "...+00:00".
    reminder = payload["reminder"]
    assert reminder["id"] == created["id"]
    assert reminder["title"] == created["title"]
    assert reminder["status"] == created["status"] == "scheduled"
    assert datetime.fromisoformat(reminder["due_at"]) == datetime.fromisoformat(created["due_at"])
    assert datetime.fromisoformat(reminder["fire_at"]) == datetime.fromisoformat(created["fire_at"])


@pytest.mark.asyncio
async def test_cancel_reminder_pushes_reminder_updated(client, auth_headers, monkeypatch):
    owner_id = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["id"]
    created = (
        await client.post(
            "/api/v1/reminders", json={"title": "Throwaway", "due_at_iso": "2099-08-10T15:00:00"}, headers=auth_headers
        )
    ).json()

    pushed = []

    async def fake_broadcast(user_ids, payload):
        pushed.append((user_ids, payload))

    monkeypatch.setattr(reminder_service.manager, "broadcast_to_users", fake_broadcast)

    resp = await client.delete(f"/api/v1/reminders/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    assert len(pushed) == 1
    ids, payload = pushed[0]
    assert ids == [owner_id]
    assert payload["type"] == "reminder_updated"
    assert payload["reminder"]["id"] == created["id"]
    assert payload["reminder"]["status"] == "cancelled"
