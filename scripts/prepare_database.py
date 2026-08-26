"""Prepare fresh, Alembic-managed, and pre-Alembic deployment databases safely."""

import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.db.schema_health import inspect_connection_schema  # noqa: E402
from src.db.session import engine  # noqa: E402


async def _status():
    try:
        async with engine.connect() as connection:
            return await inspect_connection_schema(connection)
    finally:
        await engine.dispose()


def main() -> int:
    get_settings()  # Validate production configuration before touching the database.
    config = Config(str(REPO_ROOT / "alembic.ini"))
    before = asyncio.run(_status())
    if before.compatible and not before.current_revisions:
        print("Compatible pre-Alembic schema detected; stamping current head.")
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")

    after = asyncio.run(_status())
    if not after.compatible or not after.revision_current:
        print(
            f"Database is not ready: missing_tables={after.missing_tables}, "
            f"missing_columns={after.missing_columns}, revisions={after.current_revisions}",
            file=sys.stderr,
        )
        return 1
    print(f"Database ready at revision {', '.join(after.current_revisions)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
