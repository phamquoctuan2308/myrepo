from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.models import User
from src.db.session import get_db
from src.models.reminder_schemas import ReminderCreateRequest, ReminderOut
from src.services import reminder_service
from src.services.workspace_service import resolve_workspace_for_user

router = APIRouter()


@router.get("/reminders", response_model=list[ReminderOut])
async def list_reminders(
    workspace_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReminderOut]:
    workspace = await resolve_workspace_for_user(db, current_user.id, workspace_id)
    reminders = await reminder_service.list_reminders(
        owner_id=current_user.id, workspace_id=workspace.id, limit=limit, offset=offset
    )
    return [ReminderOut.model_validate(r, from_attributes=True) for r in reminders]


@router.post("/reminders", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    request: ReminderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReminderOut:
    workspace = await resolve_workspace_for_user(db, current_user.id, request.workspace_id)
    try:
        reminder = await reminder_service.schedule_reminder(
            workspace_id=workspace.id,
            owner_id=current_user.id,
            title=request.title,
            due_at_iso=request.due_at_iso,
            lead_minutes=request.lead_minutes,
            message=request.message,
            source="manual",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ReminderOut.model_validate(reminder, from_attributes=True)


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reminder(
    reminder_id: str,
    workspace_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    workspace = await resolve_workspace_for_user(db, current_user.id, workspace_id)
    cancelled = await reminder_service.cancel_reminder(
        reminder_id, owner_id=current_user.id, workspace_id=workspace.id
    )
    if not cancelled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
