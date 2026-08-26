"""Apply the additive agent-memory schema upgrade without deleting existing data."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect

from src.db.session import engine, init_db


async def main() -> None:
    await init_db()
    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        memory_columns = await connection.run_sync(
            lambda conn: [column["name"] for column in inspect(conn).get_columns("memories")]
        )
    print("Agent memory migration complete.")
    print(f"memory_episodes present: {'memory_episodes' in tables}")
    print(f"memories columns: {len(memory_columns)}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
