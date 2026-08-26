import logging

from googleapiclient.errors import HttpError

from src.services import calendar_service
from src.services.google_credentials import CalendarNotConnectedError

logger = logging.getLogger(__name__)


class LinkedCalendarNotConnectedError(RuntimeError):
    pass


class LinkedCalendarDeleteError(RuntimeError):
    pass


async def delete_linked_event(owner_id: str, event_id: str | None) -> None:
    """Delete a task-owned Calendar event before its database link is removed.

    A Google 404 is already the desired final state. Other failures keep the task intact so the
    caller can retry instead of silently creating an orphaned external event.
    """
    if not event_id:
        return
    try:
        await calendar_service.delete_event(owner_id, event_id)
    except CalendarNotConnectedError as exc:
        raise LinkedCalendarNotConnectedError from exc
    except HttpError as exc:
        if exc.resp.status != 404:
            logger.exception("Could not delete Calendar event linked to task for user %s", owner_id)
            raise LinkedCalendarDeleteError from exc
    except Exception as exc:  # noqa: BLE001 - normalize provider/client failures for the API
        logger.exception("Could not delete Calendar event linked to task for user %s", owner_id)
        raise LinkedCalendarDeleteError from exc
