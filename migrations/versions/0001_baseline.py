"""Reconstruct the 21 public business tables from the dated catalog."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    sql_path = Path(__file__).parent.parent / ("baseline_" + connection.dialect.name + ".sql")
    for statement in sql_path.read_text(encoding="utf-8").split("\n-- next statement\n"):
        connection.exec_driver_sql(statement.strip(), execution_options={"no_parameters": True})


def downgrade():
    raise RuntimeError("Restore the pre-migration backup to roll back the baseline.")

