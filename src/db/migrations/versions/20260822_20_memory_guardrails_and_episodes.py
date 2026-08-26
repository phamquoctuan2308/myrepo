"""Add memory maintenance/guardrail fields to memories, the memory_episodes table, and the
session-compaction columns on assistant_threads (ported alongside guardrail_node/memory_tool
from the docs/branches/G19-T132-Luong-Tri-Tue.md line of work). The dev/test-only `init_db()` path
(src/db/session.py:_apply_legacy_schema_compatibility) already patches a freshly created or legacy
SQLite/dev database with the same additive columns; this migration is the equivalent for
production/staging Postgres, where init_db() is skipped and only `alembic upgrade head` runs.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260822_20"
down_revision = "20260813_12"
branch_labels = None
depends_on = None

_MEMORY_COLUMNS = (
    # (name, column factory, index name or None)
    ("status", lambda: sa.Column("status", sa.String(), nullable=False, server_default="active"), "ix_memories_status"),
    ("source_type", lambda: sa.Column("source_type", sa.String(), nullable=False, server_default="manual"), None),
    ("source_id", lambda: sa.Column("source_id", sa.String(), nullable=True), None),
    ("source_thread_id", lambda: sa.Column("source_thread_id", sa.String(), nullable=True), "ix_memories_source_thread_id"),
    ("provenance", lambda: sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"), None),
    ("importance", lambda: sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"), None),
    ("user_confirmed", lambda: sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default=sa.true()), None),
    ("access_count", lambda: sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"), None),
    ("content_hash", lambda: sa.Column("content_hash", sa.String(), nullable=False, server_default=""), "ix_memories_content_hash"),
    ("embedding", lambda: sa.Column("embedding", sa.JSON(), nullable=True), None),
    ("embedding_model", lambda: sa.Column("embedding_model", sa.String(), nullable=True), None),
)

_THREAD_COLUMNS = (
    ("session_summary", lambda: sa.Column("session_summary", sa.Text(), nullable=False, server_default="")),
    ("compacted_message_count", lambda: sa.Column("compacted_message_count", sa.Integer(), nullable=False, server_default="0")),
    ("summary_updated_at", lambda: sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True)),
    ("last_memory_maintenance_at", lambda: sa.Column("last_memory_maintenance_at", sa.DateTime(timezone=True), nullable=True)),
)

# remember_fact (src/agents/tools/memory_tool.py) writes memory_type values outside the original
# auto-extracted vocabulary; ck_memory_type (20260813_12_timeline_memory.py) must allow both.
_OLD_MEMORY_TYPES = "'preference', 'relationship', 'episodic', 'semantic'"
_NEW_MEMORY_TYPES = (
    "'preference', 'relationship', 'episodic', 'semantic', "
    "'fact', 'entity', 'decision', 'open_loop', 'knowledge', 'procedural'"
)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    memory_columns = {column["name"] for column in inspector.get_columns("memories")}
    with op.batch_alter_table("memories") as batch_op:
        for name, make_column, _ in _MEMORY_COLUMNS:
            if name not in memory_columns:
                batch_op.add_column(make_column())

    memory_check_names = {
        constraint.get("name") for constraint in inspector.get_check_constraints("memories")
    }
    if "ck_memory_type" in memory_check_names:
        with op.batch_alter_table("memories") as batch_op:
            batch_op.drop_constraint("ck_memory_type", type_="check")
            batch_op.create_check_constraint(
                "ck_memory_type", f"memory_type IN ({_NEW_MEMORY_TYPES})"
            )

    memory_index_names = {index["name"] for index in inspector.get_indexes("memories")}
    with op.batch_alter_table("memories") as batch_op:
        for name, _, index_name in _MEMORY_COLUMNS:
            if index_name and index_name not in memory_index_names:
                batch_op.create_index(index_name, [name], unique=False)

    if "memory_episodes" not in inspector.get_table_names():
        op.create_table(
            "memory_episodes",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=False),
            sa.Column("thread_id", sa.String(), nullable=True),
            sa.Column("conversation_id", sa.String(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("decisions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("open_loops", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("source_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
            sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding", sa.JSON(), nullable=True),
            sa.Column("embedding_model", sa.String(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_memory_episodes_owner_id", "memory_episodes", ["owner_id"], unique=False)
        op.create_index("ix_memory_episodes_thread_id", "memory_episodes", ["thread_id"], unique=False)
        op.create_index(
            "ix_memory_episodes_conversation_id", "memory_episodes", ["conversation_id"], unique=False
        )

    thread_columns = {column["name"] for column in inspector.get_columns("assistant_threads")}
    with op.batch_alter_table("assistant_threads") as batch_op:
        for name, make_column in _THREAD_COLUMNS:
            if name not in thread_columns:
                batch_op.add_column(make_column())


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    thread_columns = {column["name"] for column in inspector.get_columns("assistant_threads")}
    with op.batch_alter_table("assistant_threads") as batch_op:
        for name, _ in reversed(_THREAD_COLUMNS):
            if name in thread_columns:
                batch_op.drop_column(name)

    if "memory_episodes" in inspector.get_table_names():
        op.drop_index("ix_memory_episodes_conversation_id", table_name="memory_episodes")
        op.drop_index("ix_memory_episodes_thread_id", table_name="memory_episodes")
        op.drop_index("ix_memory_episodes_owner_id", table_name="memory_episodes")
        op.drop_table("memory_episodes")

    memory_index_names = {index["name"] for index in inspector.get_indexes("memories")}
    with op.batch_alter_table("memories") as batch_op:
        for _, _, index_name in _MEMORY_COLUMNS:
            if index_name and index_name in memory_index_names:
                batch_op.drop_index(index_name)

    memory_check_names = {
        constraint.get("name") for constraint in inspector.get_check_constraints("memories")
    }
    if "ck_memory_type" in memory_check_names:
        with op.batch_alter_table("memories") as batch_op:
            batch_op.drop_constraint("ck_memory_type", type_="check")
            batch_op.create_check_constraint(
                "ck_memory_type", f"memory_type IN ({_OLD_MEMORY_TYPES})"
            )

    memory_columns = {column["name"] for column in inspector.get_columns("memories")}
    with op.batch_alter_table("memories") as batch_op:
        for name, _, _ in reversed(_MEMORY_COLUMNS):
            if name in memory_columns:
                batch_op.drop_column(name)
