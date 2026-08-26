import importlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select

from src.db import session as db_session
from src.db.models import MigrationState, User, Workspace


def _migration_service():
    try:
        return importlib.import_module("src.services.migration_service")
    except ModuleNotFoundError:
        pytest.fail("workspace migration service is not implemented")


async def _register(client, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_preflight_rejects_multiple_admins_without_config(client):
    first = await _register(client, "first-admin@example.com")
    second = await _register(client, "second-admin@example.com")
    async with db_session.async_session_maker() as db:
        for user_id in (first["id"], second["id"]):
            user = await db.get(User, user_id)
            user.role = "admin"
        await db.commit()

        report = await _migration_service().preflight_workspace_migration(db, bootstrap_owner_user_id=None)

    assert report.can_run is False
    assert report.owner_user_id is None
    assert report.error_code == "ambiguous_bootstrap_owner"


@pytest.mark.asyncio
async def test_preflight_selects_only_active_admin(client):
    admin = await _register(client, "only-admin@example.com")
    async with db_session.async_session_maker() as db:
        user = await db.get(User, admin["id"])
        user.role = "admin"
        await db.commit()

        report = await _migration_service().preflight_workspace_migration(db, bootstrap_owner_user_id=None)

    assert report.can_run is True
    assert report.owner_user_id == admin["id"]
    assert report.error_code is None


@pytest.mark.asyncio
async def test_workspace_migration_dry_run_does_not_write(client):
    admin = await _register(client, "dry-run-admin@example.com")
    async with db_session.async_session_maker() as db:
        user = await db.get(User, admin["id"])
        user.role = "admin"
        personal_workspaces = (
            (await db.execute(select(Workspace).where(Workspace.personal_owner_user_id == admin["id"]))).scalars().all()
        )
        for workspace in personal_workspaces:
            await db.delete(workspace)
        await db.commit()

        report = await _migration_service().run_workspace_foundation_backfill(
            db,
            bootstrap_owner_user_id=None,
            dry_run=True,
        )
        workspace_count = (await db.execute(select(func.count()).select_from(Workspace))).scalar_one()

    assert report.can_run is True
    assert report.owner_user_id == admin["id"]
    assert workspace_count == 0


def _create_legacy_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id VARCHAR PRIMARY KEY,
            email VARCHAR NOT NULL UNIQUE,
            password_hash VARCHAR NOT NULL,
            display_name VARCHAR NOT NULL,
            role VARCHAR NOT NULL DEFAULT 'user',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL
        );
        CREATE TABLE conversations (
            id VARCHAR PRIMARY KEY,
            type VARCHAR NOT NULL,
            name VARCHAR,
            created_by VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE conversation_participants (
            conversation_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            joined_at DATETIME NOT NULL,
            last_read_at DATETIME NOT NULL,
            PRIMARY KEY (conversation_id, user_id)
        );
        CREATE TABLE messages (
            id VARCHAR PRIMARY KEY,
            conversation_id VARCHAR NOT NULL,
            sender_id VARCHAR NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME NOT NULL
        );
        INSERT INTO users VALUES
            ('admin-1', 'admin@example.com', 'hash', 'Admin', 'admin', 1, '2026-08-01 00:00:00'),
            ('member-1', 'member@example.com', 'hash', 'Member', 'user', 1, '2026-08-01 00:00:00');
        INSERT INTO conversations VALUES
            ('conversation-1', 'direct', NULL, 'admin-1', '2026-08-01 00:00:00', '2026-08-01 00:00:00');
        INSERT INTO conversation_participants VALUES
            ('conversation-1', 'admin-1', '2026-08-01 00:00:00', '2026-08-01 00:00:00'),
            ('conversation-1', 'member-1', '2026-08-01 00:00:00', '2026-08-01 00:00:00');
        """
    )
    connection.commit()
    connection.close()


def test_alembic_upgrade_backfills_workspace_foundation_idempotently(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    _create_legacy_database(database_path)
    monkeypatch.setenv("BOOTSTRAP_OWNER_USER_ID", "admin-1")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    connection = sqlite3.connect(database_path)
    personal_count = connection.execute("SELECT COUNT(*) FROM workspaces WHERE type = 'personal'").fetchone()[0]
    organization = connection.execute(
        "SELECT id FROM workspaces WHERE type = 'organization' AND slug = 'legacy-organization'"
    ).fetchone()
    assert organization is not None
    owner_role = connection.execute(
        "SELECT role FROM workspace_memberships WHERE workspace_id = ? AND user_id = 'admin-1'",
        (organization[0],),
    ).fetchone()[0]
    conversation_workspace = connection.execute(
        "SELECT workspace_id FROM conversations WHERE id = 'conversation-1'"
    ).fetchone()[0]
    platform_role = connection.execute("SELECT platform_role FROM users WHERE id = 'admin-1'").fetchone()[0]
    connection.close()

    assert personal_count == 2
    assert owner_role == "owner"
    assert conversation_workspace == organization[0]
    assert platform_role == "platform_admin"


def test_alembic_upgrade_builds_fresh_database(tmp_path):
    database_path = tmp_path / "fresh.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")

    connection = sqlite3.connect(database_path)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    connection.close()

    assert {
        "users",
        "workspaces",
        "workspace_memberships",
        "external_contacts",
        "contact_relationships",
        "conversations",
        "conversation_participants",
        "messages",
    }.issubset(tables)
    assert {
        "tasks",
        "usage_logs",
        "memories",
        "calendar_sync_state",
        "reminders",
        "event_candidates",
        "event_extraction_cursors",
        "assistant_threads",
        "conversation_rolling_summaries",
    }.issubset(tables)
    assert "people_preferences" in tables
    assert revision == "20260824_19"
    assert "agent_threads" in tables
    assert {"google_identities", "ai_permissions"}.issubset(tables)


def test_prepare_database_stamps_compatible_pre_alembic_schema(tmp_path):
    database_path = tmp_path / "create-all.db"
    sync_engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    from src.db.base import Base

    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    environment["APP_ENV"] = "test"

    result = subprocess.run(
        [sys.executable, "scripts/prepare_database.py"],
        cwd=Path(__file__).parent.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Compatible pre-Alembic schema detected" in result.stdout
    connection = sqlite3.connect(database_path)
    revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    connection.close()
    assert revision == "20260824_19"


@pytest.mark.asyncio
async def test_migration_state_updates_one_record_across_transitions(client):
    async with db_session.async_session_maker() as db:
        running = await _migration_service().set_workspace_migration_state(db, status="running")
        await db.commit()
        migration_state_id = running.id

        failed = await _migration_service().set_workspace_migration_state(
            db,
            status="failed",
            error_code="alembic_upgrade_failed",
        )
        await db.commit()
        assert failed.id == migration_state_id
        assert failed.completed_at is None

        completed = await _migration_service().set_workspace_migration_state(db, status="completed")
        await db.commit()
        states = (await db.execute(select(MigrationState))).scalars().all()

    assert completed.id == migration_state_id
    assert completed.error_code is None
    assert completed.completed_at is not None
    assert len(states) == 1


def test_workspace_migration_cli_dry_run_reports_without_writing(tmp_path):
    database_path = tmp_path / "legacy-cli.db"
    _create_legacy_database(database_path)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    environment["BOOTSTRAP_OWNER_USER_ID"] = "admin-1"

    result = subprocess.run(
        [sys.executable, "scripts/migrate_workspace_foundation.py", "--dry-run"],
        cwd=Path(__file__).parent.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["can_run"] is True
    assert report["owner_user_id"] == "admin-1"
    connection = sqlite3.connect(database_path)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    connection.close()
    assert "workspaces" not in tables
    assert "migration_states" not in tables
