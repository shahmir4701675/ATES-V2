"""Configure whole-slot lab block lengths with the timetable solver settings."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("scheduling_configs", sa.Column(
        "lab_block_slots", sa.SmallInteger(), sa.CheckConstraint("lab_block_slots BETWEEN 1 AND 48")
    ))


def downgrade():
    op.drop_column("scheduling_configs", "lab_block_slots")

