from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.db.base import Base


@dataclass(frozen=True)
class SchemaStatus:
    compatible: bool
    revision_current: bool
    current_revisions: tuple[str, ...]
    expected_revisions: tuple[str, ...]
    missing_tables: tuple[str, ...]
    missing_columns: tuple[str, ...]


def expected_revisions() -> tuple[str, ...]:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    return tuple(sorted(ScriptDirectory.from_config(config).get_heads()))


def _inspect_schema(connection: Connection) -> SchemaStatus:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            missing_tables.append(table.name)
            continue
        actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing_columns.extend(
            f"{table.name}.{column.name}" for column in table.columns if column.name not in actual_columns
        )

    revisions: tuple[str, ...] = ()
    if "alembic_version" in existing_tables:
        revisions = tuple(
            sorted(str(value) for value in connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
        )
    expected = expected_revisions()
    return SchemaStatus(
        compatible=not missing_tables and not missing_columns,
        revision_current=revisions == expected,
        current_revisions=revisions,
        expected_revisions=expected,
        missing_tables=tuple(sorted(missing_tables)),
        missing_columns=tuple(sorted(missing_columns)),
    )


async def inspect_connection_schema(connection: AsyncConnection) -> SchemaStatus:
    return await connection.run_sync(_inspect_schema)


async def inspect_session_schema(session: AsyncSession) -> SchemaStatus:
    connection = await session.connection()
    return await inspect_connection_schema(connection)
