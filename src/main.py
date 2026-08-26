import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.graph import close_checkpointer, init_checkpointer
from src.api.admin_routes import router as admin_router
from src.api.assistant_routes import router as assistant_router
from src.api.auth_routes import router as auth_router
from src.api.calendar_routes import public_router as calendar_public_router
from src.api.calendar_routes import router as calendar_router
from src.api.chat_routes import router as chat_router
from src.api.memory_routes import router as memory_router
from src.api.platform_routes import router as platform_router
from src.api.rate_limit import RateLimitMiddleware
from src.api.reminder_routes import router as reminder_router
from src.api.routes import router
from src.api.task_routes import router as task_router
from src.api.timeline_routes import router as timeline_router
from src.api.workspace_routes import router as workspace_router
from src.config import get_settings
from src.db.schema_health import inspect_session_schema
from src.db.session import get_db, init_db
from src.services import (
    calendar_service,
    conversation_summary_service,
    memory_maintenance_service,
    thread_memory_service,
)
from src.services.ai_config_service import load_saved_ai_configuration
from src.services.scheduler import scheduler
from src.websocket.routes import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    if settings.app_env != "production":
        await init_db()
    await load_saved_ai_configuration()
    await init_checkpointer()
    await thread_memory_service.cleanup_expired_threads()
    scheduler.start()
    scheduler.add_job(
        thread_memory_service.cleanup_expired_threads,
        "interval",
        hours=1,
        id="agent_thread_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        calendar_service.poll_calendar_changes,
        "interval",
        seconds=settings.calendar_poll_interval_seconds,
        id="calendar_poll",
        replace_existing=True,
    )
    scheduler.add_job(
        memory_maintenance_service.heartbeat,
        "interval",
        seconds=settings.memory_heartbeat_interval_seconds,
        id="memory_heartbeat",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    if settings.conversation_summary_enabled:
        scheduler.add_job(
            conversation_summary_service.heartbeat,
            "interval",
            seconds=settings.conversation_summary_interval_seconds,
            id="conversation_summary_heartbeat",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    yield
    scheduler.shutdown(wait=False)
    await close_checkpointer()
    print("Shutting down...")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(ws_router, prefix="/api/v1", tags=["ws"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(platform_router, prefix="/api/v1/platform", tags=["platform"])
app.include_router(workspace_router, prefix="/api/v1/workspaces", tags=["workspaces"])
app.include_router(task_router, prefix="/api/v1", tags=["tasks"])
app.include_router(timeline_router, prefix="/api/v1", tags=["timeline"])
app.include_router(calendar_router, prefix="/api/v1", tags=["calendar"])
app.include_router(calendar_public_router, prefix="/api/v1", tags=["calendar"])
app.include_router(reminder_router, prefix="/api/v1", tags=["reminders"])
app.include_router(memory_router, prefix="/api/v1", tags=["memory"])
app.include_router(assistant_router, prefix="/api/v1", tags=["assistant"])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    try:
        schema = await inspect_session_schema(db)
    except Exception:  # noqa: BLE001 - readiness must fail closed without leaking DB details
        logging.exception("Database readiness check failed")
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "not_ready"})
    revision_required = settings.app_env == "production"
    ready = schema.compatible and (schema.revision_current or not revision_required)
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "not_ready"},
    )
