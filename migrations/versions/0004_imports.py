"""Stage a CSV preview separately from the business records it may create."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staged_imports",
        sa.Column("import_key", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entity", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(120), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("preview", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('Pending', 'Confirmed', 'Cancelled')"),
    )
    op.create_index("ix_staged_imports_user_id", "staged_imports", ["user_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE staged_imports ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_table("staged_imports")

