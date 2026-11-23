"""Persist run ownership, snapshots and the logical identity of multi-slot sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("timetable_entries", sa.Column("session_key", sa.String(48)))
    op.create_index("ix_timetable_entries_logical", "timetable_entries", ["schedule_id", "session_key"])
    op.create_table(
        "schedule_runs",
        sa.Column("schedule_id", sa.Integer, sa.ForeignKey("schedules.schedule_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("request_token", sa.String(36), unique=True, nullable=False),
        sa.Column("input_snapshot", sa.JSON, nullable=False),
        sa.Column("baseline", sa.JSON),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("claim_id", sa.String(36)),
        sa.Column("started_at", sa.DateTime),
        sa.Column("heartbeat_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("outcome", sa.Text),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE schedule_runs ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table("schedule_runs")
    op.drop_index("ix_timetable_entries_logical", table_name="timetable_entries")
    op.drop_column("timetable_entries", "session_key")

