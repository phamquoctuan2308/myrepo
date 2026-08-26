"""Add consent-scoped rolling summary table for 1-1/group Conversation chats."""

import sqlalchemy as sa
from alembic import op

revision = "20260823_18"
down_revision = "20260822_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    if "conversation_rolling_summaries" not in tables:
        op.create_table(
            "conversation_rolling_summaries",
            sa.Column("conversation_id", sa.String(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("last_message_created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_message_id", sa.String(), nullable=True),
            sa.Column("processed_message_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("needs_reset", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
            sa.PrimaryKeyConstraint("conversation_id"),
        )


def downgrade() -> None:
    op.drop_table("conversation_rolling_summaries")
