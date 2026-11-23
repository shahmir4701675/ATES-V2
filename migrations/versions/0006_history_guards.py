"""Check both source and destination when database entries change versions."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION public.fn_prevent_published_schedule_entry_edit()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = public, pg_temp
        AS $function$
        DECLARE
            source_version INTEGER;
            destination_version INTEGER;
        BEGIN
            IF TG_TABLE_NAME = 'exam_room_allocations' THEN
                IF TG_OP <> 'INSERT' THEN
                    SELECT schedule_id INTO source_version FROM exam_entries WHERE exam_entry_id = OLD.exam_entry_id;
                END IF;
                IF TG_OP <> 'DELETE' THEN
                    SELECT schedule_id INTO destination_version FROM exam_entries WHERE exam_entry_id = NEW.exam_entry_id;
                END IF;
            ELSE
                IF TG_OP <> 'INSERT' THEN source_version := OLD.schedule_id; END IF;
                IF TG_OP <> 'DELETE' THEN destination_version := NEW.schedule_id; END IF;
            END IF;
            IF EXISTS (
                SELECT 1 FROM schedules
                WHERE schedule_id IN (source_version, destination_version) AND status IN ('Published', 'Archived')
            ) THEN
                RAISE EXCEPTION 'Published and archived entries are read-only.';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $function$
    """)


def downgrade():
    raise RuntimeError("Restore the pre-migration backup to revert schedule history guards.")

