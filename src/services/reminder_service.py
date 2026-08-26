import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.config import get_settings
from src.db import session as db_session
from src.db.models import Reminder
from src.services.scheduler import scheduler
from src.websocket.manager import manager

logger = logging.getLogger(__name__)


def _reminder_payload(reminder: Reminder) -> dict:
    return {
        "id": reminder.id,
        "title": reminder.title,
        "message": reminder.message,
        "due_at": reminder.due_at.isoformat(),
        "fire_at": reminder.fire_at.isoformat(),
        "status": reminder.status,
        "source": reminder.source,
        "created_at": reminder.created_at.isoformat(),
    }


async def schedule_reminder(
    *,
    workspace_id: str,
    owner_id: str,
    title: str,
    due_at_iso: str | datetime,
    lead_minutes: int = 30,
    message: str = "",
    source: str = "manual",
) -> Reminder:
    if not workspace_id or not owner_id:
        raise ValueError("Reminder workspace and owner are required")
    due_at = due_at_iso if isinstance(due_at_iso, datetime) else datetime.fromisoformat(due_at_iso)
    if due_at.tzinfo is None:
        # The agent/LLM sometimes emits a date/time with no UTC offset - treat it as Hanoi
        # time (not the server's local zone) rather than storing an ambiguous naive value.
        due_at = due_at.replace(tzinfo=ZoneInfo(get_settings().scheduler_timezone))
    fire_at = due_at - timedelta(minutes=lead_minutes)
    now = datetime.now(UTC)
    if due_at.astimezone(UTC) <= now:
        raise ValueError("Reminder due time must be in the future")
    if fire_at.astimezone(UTC) <= now:
        raise ValueError("Reminder notification time must be in the future")

    async with db_session.async_session_maker() as db:
        reminder = Reminder(
            workspace_id=workspace_id,
            owner_id=owner_id,
            title=title,
            message=message,
            due_at=due_at,
            fire_at=fire_at,
            source=source,
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)

    scheduler.add_job(_fire_reminder_job, "date", run_date=fire_at, args=[reminder.id], id=reminder.id)
    # Realtime: pushed regardless of who/what created it (this UI's "New reminder", the agent's
    # create_reminder tool, or an Accepted proactive task auto-creating one) - same reasoning as
    # calendar_service.broadcast_change, so ReminderPage.jsx reflects it live in every open tab,
    # not just the one that made the request.
    if owner_id:
        await manager.broadcast_to_users(
            [owner_id], {"type": "reminder_created", "reminder": _reminder_payload(reminder)}
        )
    return reminder


async def _fire_reminder_job(reminder_id: str) -> None:
    """APScheduler job callback executed when a reminder's lead time elapses."""
    async with db_session.async_session_maker() as db:
        reminder = await db.get(Reminder, reminder_id)
        if reminder is None or reminder.status != "scheduled":
            return
        reminder.status = "fired"
        await db.commit()
        owner_id, workspace_id, title, message = (
            reminder.owner_id,
            reminder.workspace_id,
            reminder.title,
            reminder.message,
        )

    logger.info("Reminder fired: %s (%s)", title, reminder_id)
    if owner_id:
        await manager.broadcast_to_users(
            [owner_id],
            {
                "type": "reminder_fired",
                "workspace_id": workspace_id,
                "reminder": {
                    "id": reminder_id,
                    "workspace_id": workspace_id,
                    "title": title,
                    "message": message,
                },
            },
        )


async def list_reminders(
    owner_id: str,
    workspace_id: str,
    limit: int = 200,
    offset: int = 0,
) -> list[Reminder]:
    async with db_session.async_session_maker() as db:
        result = await db.execute(
            select(Reminder)
            .where(Reminder.owner_id == owner_id, Reminder.workspace_id == workspace_id)
            .order_by(Reminder.fire_at)
            .offset(max(0, offset))
            .limit(max(1, min(limit, 500)))
        )
        return list(result.scalars().all())


def remove_scheduler_job(reminder_id: str) -> None:
    try:
        scheduler.remove_job(reminder_id)
    except Exception:  # noqa: BLE001 - job may already have fired/been removed
        pass


async def cancel_reminder(reminder_id: str, owner_id: str, workspace_id: str) -> bool:
    async with db_session.async_session_maker() as db:
        reminder = (
            await db.execute(
                select(Reminder).where(
                    Reminder.id == reminder_id,
                    Reminder.owner_id == owner_id,
                    Reminder.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()
        if reminder is None:
            return False
        if reminder.status == "scheduled":
            remove_scheduler_job(reminder_id)
        reminder.status = "cancelled"
        await db.commit()
        await db.refresh(reminder)
    # "reminder_updated" (not a distinct event type) - ReminderPage.jsx keeps a cancelled row
    # visible with its badge changed, the same upsert-in-place treatment task_updated gets for a
    # dismissed/completed Task, rather than removing it from the list.
    await manager.broadcast_to_users([owner_id], {"type": "reminder_updated", "reminder": _reminder_payload(reminder)})
    return True
