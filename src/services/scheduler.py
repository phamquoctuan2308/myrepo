from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.pool import NullPool

from src.config import get_settings

settings = get_settings()


def _sync_jobstore_url(url: str) -> str:
    """Return a sync psycopg URL for APScheduler's SQLAlchemy job store.

    The rest of the application uses asyncpg, and some deployments therefore
    provide DATABASE_URL with an explicit ``postgresql+asyncpg://`` scheme.
    SQLAlchemyJobStore is synchronous, so allowing that scheme through makes it
    attempt async I/O outside a greenlet during application startup.
    """
    scheme, separator, rest = url.partition("://")
    if separator and scheme in {"postgresql", "postgresql+asyncpg"}:
        return f"postgresql+psycopg://{rest}"
    return url


# SQLAlchemyJobStore uses a *sync* engine, so it needs its own driver: psycopg2 (default for
# "postgresql://") isn't installed, but psycopg3 is (already pulled in for the LangGraph
# checkpointer) - point it at that dialect instead of adding another dependency. Normalize an
# explicit asyncpg URL too, since DATABASE_URL is shared with the application's async engine.
_jobstore_url = _sync_jobstore_url(settings.database_url)

# SQLAlchemyJobStore persists scheduled jobs (e.g. reminders) so they survive a server restart -
# without it, a job's row in the DB could say "scheduled" while the actual APScheduler job that
# would fire it is gone, and it would just never fire.
# timezone=... matters even though the datetimes passed in are usually tz-aware already: without
# it, APScheduler falls back to the *system's* local timezone (often UTC on a server) for any
# naive datetime it's given, which would fire reminders up to 7h off from Hanoi time.
# engine_options caps this jobstore's own pool - it's the third of three pools sharing a managed
# Postgres pooler's total-client budget (e.g. Supabase Session pooler caps ~15), alongside
# session.py's engine and graph.py's AsyncPostgresSaver pool. SQLAlchemy's sync default (5 +
# 10 overflow = 15) would exhaust that budget on its own.
scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=_jobstore_url, engine_options={"poolclass": NullPool})},
    timezone=settings.scheduler_timezone,
)
