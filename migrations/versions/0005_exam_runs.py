"""Store exam inclusion choices, run statistics and manual-override state."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exam_entries", sa.Column("is_manual_override", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("schedule_runs", sa.Column("statistics", sa.JSON))
    op.create_table(
        "term_exam_exclusions",
        sa.Column("term_id", sa.Integer, sa.ForeignKey("academic_terms.term_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.course_id", ondelete="RESTRICT"), primary_key=True),
    )
    op.create_index("ix_term_exam_exclusions_course_id", "term_exam_exclusions", ["course_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE term_exam_exclusions ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table("term_exam_exclusions")
    op.drop_column("schedule_runs", "statistics")
    op.drop_column("exam_entries", "is_manual_override")

