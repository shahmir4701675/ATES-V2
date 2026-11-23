"""Add revocable sessions and the locally rehearsed composite FK index."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_last_seen_at", "user_sessions", ["last_seen_at"])
    op.create_index(
        "ix_timetable_entries_offering_instructor_batch",
        "timetable_entries",
        ["offering_id", "instructor_id", "batch_id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_index("ix_timetable_entries_offering_instructor_batch", table_name="timetable_entries")
    op.drop_table("user_sessions")

