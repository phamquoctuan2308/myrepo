"""Add Task.calendar_event_id so accepting an AI-suggested task can auto-sync to Google Calendar."""

import sqlalchemy as sa
from alembic import op

revision = "20260824_19"
down_revision = "20260823_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    task_columns = {c["name"] for c in inspector.get_columns("tasks")}
    if "calendar_event_id" not in task_columns:
        op.add_column("tasks", sa.Column("calendar_event_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "calendar_event_id")
