from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from src.config import get_settings
from src.db import session as db_session
from src.db.models import Task
from src.services import calendar_service


async def _create_proactive_task(client, auth_headers, *, title, due_at=None):
    created = (
        await client.post(
            "/api/v1/tasks",
            json={"title": title, "due_at": due_at, "source": "manual"},
            headers=auth_headers,
        )
    ).json()
    async with db_session.async_session_maker() as db:
        task = (await db.execute(select(Task).where(Task.id == created["id"]))).scalar_one()
        task.source = "proactive"
        task.status = "suggested"
        await db.commit()
    tasks = (await client.get("/api/v1/tasks", headers=auth_headers)).json()
    return next(task for task in tasks if task["id"] == created["id"])


@pytest.mark.asyncio
async def test_create_and_list_task(client, auth_headers):
    resp = await client.post(
        "/api/v1/tasks", json={"title": "Send report", "priority": "High"}, headers=auth_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Send report"
    assert body["priority"] == "High"
    assert body["status"] == "pending"
    assert body["source"] == "manual"
    assert body["source"] == "manual"

    resp = await client.get("/api/v1/tasks", headers=auth_headers)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Send report" in titles


@pytest.mark.asyncio
async def test_tasks_require_auth(client):
    resp = await client.get("/api/v1/tasks")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_task_status(client, auth_headers):
    created = (
        await client.post("/api/v1/tasks", json={"title": "Book flight"}, headers=auth_headers)
    ).json()

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}/status", json={"status": "pending"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_delete_task(client, auth_headers):
    created = (
        await client.post("/api/v1/tasks", json={"title": "Throwaway"}, headers=auth_headers)
    ).json()

    resp = await client.delete(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/tasks", headers=auth_headers)
    assert created["id"] not in [t["id"] for t in resp.json()]


@pytest.mark.asyncio
async def test_delete_synced_task_deletes_calendar_event_first(client, auth_headers, monkeypatch):
    created = (
        await client.post("/api/v1/tasks", json={"title": "Synced task"}, headers=auth_headers)
    ).json()
    async with db_session.async_session_maker() as db:
        task = await db.get(Task, created["id"])
        task.calendar_event_id = "event-linked"
        await db.commit()
    delete_event = AsyncMock()
    monkeypatch.setattr(calendar_service, "delete_event", delete_event)

    response = await client.delete(f"/api/v1/tasks/{created['id']}", headers=auth_headers)

    assert response.status_code == 204
    delete_event.assert_awaited_once()
    assert created["id"] not in [item["id"] for item in (await client.get("/api/v1/tasks", headers=auth_headers)).json()]


@pytest.mark.asyncio
async def test_delete_synced_task_keeps_task_when_calendar_delete_fails(client, auth_headers, monkeypatch):
    created = (
        await client.post("/api/v1/tasks", json={"title": "Retry delete"}, headers=auth_headers)
    ).json()
    async with db_session.async_session_maker() as db:
        task = await db.get(Task, created["id"])
        task.calendar_event_id = "event-fails"
        await db.commit()
    monkeypatch.setattr(calendar_service, "delete_event", AsyncMock(side_effect=RuntimeError("provider secret")))

    response = await client.delete(f"/api/v1/tasks/{created['id']}", headers=auth_headers)

    assert response.status_code == 502
    assert "provider secret" not in response.text
    assert created["id"] in [item["id"] for item in (await client.get("/api/v1/tasks", headers=auth_headers)).json()]


@pytest.mark.asyncio
async def test_task_not_visible_to_other_user(client, auth_headers, other_auth_headers):
    created = (
        await client.post("/api/v1/tasks", json={"title": "Private task"}, headers=auth_headers)
    ).json()

    resp = await client.get("/api/v1/tasks", headers=other_auth_headers)
    assert created["id"] not in [t["id"] for t in resp.json()]

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}/status", json={"status": "dismissed"}, headers=other_auth_headers
    )
    assert resp.status_code == 404

    resp = await client.delete(f"/api/v1/tasks/{created['id']}", headers=other_auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_task_with_naive_due_at_is_localized_to_calendar_timezone(client, auth_headers):
    """A due_at with no UTC offset (what the LLM emits, e.g. via AIPanel's "Extract tasks" posting
    it straight to this endpoint) must be interpreted as calendar_timezone - not left for
    Postgres/asyncpg to guess from the DB server's own session timezone, which only happens to
    match by coincidence on any given machine. Regression test for task_routes.py::create_task."""
    resp = await client.post(
        "/api/v1/tasks",
        json={"title": "Naive due date", "due_at": "2026-08-10T15:00:00", "priority": "Medium"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    due_at = datetime.fromisoformat(resp.json()["due_at"])
    assert due_at.tzinfo is not None
    assert due_at == datetime(2026, 8, 10, 15, 0, tzinfo=ZoneInfo(get_settings().calendar_timezone))


@pytest.mark.asyncio
async def test_create_task_with_offset_due_at_is_kept_as_is(client, auth_headers):
    """A due_at that already carries an explicit UTC offset must not be re-localized/shifted."""
    resp = await client.post(
        "/api/v1/tasks",
        json={"title": "Explicit offset due date", "due_at": "2026-08-10T15:00:00+00:00", "priority": "Medium"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    due_at = datetime.fromisoformat(resp.json()["due_at"])
    assert due_at == datetime(2026, 8, 10, 15, 0, tzinfo=ZoneInfo("UTC"))


@pytest.mark.asyncio
async def test_tasks_sorted_by_due_date_then_priority(client, auth_headers):
    await client.post(
        "/api/v1/tasks",
        json={"title": "No due date", "priority": "High"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/tasks",
        json={"title": "Due soon", "due_at": "2026-01-01T00:00:00Z", "priority": "Low"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/tasks",
        json={"title": "Due later", "due_at": "2026-06-01T00:00:00Z", "priority": "High"},
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/tasks", headers=auth_headers)
    titles = [t["title"] for t in resp.json()]
    assert titles == ["Due soon", "Due later", "No due date"]


@pytest.mark.asyncio
async def test_accepting_proactive_task_auto_syncs_calendar_but_not_reminder(
    client, auth_headers, monkeypatch
):
    """Product decision: Accept on an AI-suggested task IS the human confirmation to write the
    matching Google Calendar event (no separate dialog) - but it still must not silently create
    a Reminder, which has its own distinct confirmation flow."""
    fake_service = MagicMock()
    fake_service.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt-1", "htmlLink": "https://calendar.google.com/event?eid=evt1",
    }
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: fake_service)

    created = await _create_proactive_task(
        client, auth_headers, title="Product launch call", due_at="2026-08-10T15:00:00"
    )
    assert created["status"] == "suggested"

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}/status", json={"status": "pending"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["calendar_event_id"] == "evt-1"

    fake_service.events.return_value.insert.assert_called_once()
    call_kwargs = fake_service.events.return_value.insert.call_args.kwargs
    assert call_kwargs["body"]["summary"] == "Product launch call"
    assert call_kwargs["body"]["start"]["dateTime"] == "2026-08-10T15:00:00+07:00"
    assert call_kwargs["body"]["end"]["dateTime"] == "2026-08-10T15:30:00+07:00"

    reminders = (await client.get("/api/v1/reminders", headers=auth_headers)).json()
    assert not any(r["title"] == "Product launch call" for r in reminders)


@pytest.mark.asyncio
async def test_accepting_manual_task_does_not_touch_calendar_or_reminder(client, auth_headers, monkeypatch):
    fake_service = MagicMock()
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: fake_service)

    created = (
        await client.post(
            "/api/v1/tasks",
            json={"title": "Manual with due date", "due_at": "2026-08-10T15:00:00", "source": "manual"},
            headers=auth_headers,
        )
    ).json()

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}/status", json={"status": "pending"}, headers=auth_headers
    )
    assert resp.status_code == 200
    fake_service.events.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_accepting_proactive_task_without_due_date_does_not_touch_calendar_or_reminder(
    client, auth_headers, monkeypatch
):
    fake_service = MagicMock()
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: fake_service)

    created = await _create_proactive_task(client, auth_headers, title="No due date")
    assert created["due_at"] is None

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}/status", json={"status": "pending"}, headers=auth_headers
    )
    assert resp.status_code == 200
    fake_service.events.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_accepting_proactive_task_survives_calendar_sync_failure(client, auth_headers, monkeypatch):
    """The calendar auto-sync from the test above is best-effort: a broken Google API must not
    stop Accept from succeeding, and must not fall back to creating a Reminder instead."""

    def _broken_get_calendar_service():
        raise RuntimeError("Google API unreachable")

    monkeypatch.setattr(calendar_service, "get_calendar_service", _broken_get_calendar_service)

    created = await _create_proactive_task(
        client, auth_headers, title="Flaky calendar", due_at="2026-08-10T15:00:00"
    )

    resp = await client.patch(
        f"/api/v1/tasks/{created['id']}/status", json={"status": "pending"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    reminders = (await client.get("/api/v1/reminders", headers=auth_headers)).json()
    assert not any(r["title"] == "Flaky calendar" for r in reminders)


@pytest.mark.asyncio
async def test_deleting_synced_calendar_event_dismisses_the_linked_task(client, auth_headers, monkeypatch):
    """Task <-> Calendar sync is two-way: once Accept auto-created a Calendar event for a task
    (see the accept test above), deleting that event - from the app's own Delete event button, or
    detected from Google Calendar itself via poll_calendar_changes - must not leave the task
    looking like it's still awaiting the user's attention."""
    fake_service = MagicMock()
    fake_service.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt-linked", "htmlLink": "https://calendar.google.com/event?eid=evtlinked",
    }
    monkeypatch.setattr(calendar_service, "get_calendar_service", lambda: fake_service)

    created = await _create_proactive_task(
        client, auth_headers, title="Họp ngày mai", due_at="2026-08-25T09:00:00"
    )
    accepted = (
        await client.patch(
            f"/api/v1/tasks/{created['id']}/status", json={"status": "pending"}, headers=auth_headers
        )
    ).json()
    assert accepted["calendar_event_id"] == "evt-linked"

    user_id = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["id"]
    # Exercises exactly what calendar_routes.delete_event and poll_calendar_changes both call once
    # Google confirms the event is gone - no need to re-mock the Google client for this part.
    await calendar_service.broadcast_change(user_id, "calendar_event_deleted", {"event_id": "evt-linked"})

    tasks = (await client.get("/api/v1/tasks", headers=auth_headers)).json()
    task = next(t for t in tasks if t["id"] == created["id"])
    assert task["status"] == "dismissed"
    assert task["calendar_event_id"] is None
