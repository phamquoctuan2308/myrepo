import pytest

from src.db import session as db_session
from src.db.models import AuditLog, User
from src.services.audit_service import record_audit_event


async def _make_user(db, email="admin@example.com"):
    user = User(email=email, password_hash="x", display_name="Admin", role="admin", platform_role="platform_admin")
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_record_audit_event_writes_a_row_with_admin_actor(client):
    # `client` isn't otherwise used - it's here purely for the truncate-after-test isolation its
    # fixture teardown provides (see conftest.py), since this test writes User/AuditLog rows
    # directly and doesn't go through any HTTP call that would trigger it another way.
    async with db_session.async_session_maker() as db:
        user = await _make_user(db)
        record = await record_audit_event(
            db, actor=user, action="user.role_changed", target_type="user", target_id="target-1", workspace_id=None,
            metadata={"previous": "user", "current": "admin"},
        )
        await db.commit()
        assert record.actor_type == "platform_admin"
        assert record.actor_user_id == user.id

        stored = await db.get(AuditLog, record.id)
        assert stored.action == "user.role_changed"
        assert stored.metadata_json == {"previous": "user", "current": "admin"}


@pytest.mark.asyncio
async def test_record_audit_event_system_actor_when_no_user(client):
    async with db_session.async_session_maker() as db:
        record = await record_audit_event(db, actor=None, action="scheduler.tick", target_type="system", target_id=None, workspace_id=None)
        await db.commit()
        assert record.actor_type == "system"
        assert record.actor_user_id is None


@pytest.mark.asyncio
async def test_record_audit_event_rejects_sensitive_metadata_keys(client):
    async with db_session.async_session_maker() as db:
        user = await _make_user(db)
        with pytest.raises(ValueError, match="sensitive"):
            await record_audit_event(
                db, actor=user, action="chat.message_sent", target_type="message", target_id="m1", workspace_id=None,
                metadata={"content": "this is a real chat message, must never be persisted here"},
            )
