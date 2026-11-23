"""SAF-5 local online backups, retention and isolated restore."""

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.api.app import create_app
from backend.data.backups import KARACHI, backup, restore
from backend.data.database import database
from backend.data.store import Store
from conftest import TEST_SECRET
from test_master import login
from test_versions import generate, prepare


def test_SAF_5_backup_retention_and_recovery(migrated_db, tmp_path):
    url = migrated_db.url.render_as_string(hide_password=False)
    term = prepare(url)
    store = Store(url)
    try:
        with TestClient(create_app(url, TEST_SECRET)) as client:
            generate(client, login(client, "coordinator"), store, term)
    finally:
        store.engine.dispose()
    start = datetime(2026, 11, 1, 19, tzinfo=KARACHI)
    for index in range(9):
        latest = backup(url, tmp_path, start + timedelta(days=index))
    assert len(list(tmp_path.glob("ates-backup-*.sqlite3"))) == 7

    new_file = migrated_db.url.database + "." + uuid4().hex + ".sqlite3"
    new_target = migrated_db.url.set(database=new_file)
    restore(new_target, latest)
    restored = database(new_target)
    try:
        with migrated_db.connect() as origin, restored.connect() as recovered:
            for table in ("academic_terms", "schedule_runs", "timetable_entries", "schedules", "users",
                          "scheduling_configs", "constraint_rules", "audit_logs", "alembic_version"):
                query = text(f"SELECT * FROM {table}")
                assert origin.execute(query).all() == recovered.execute(query).all()
        with TestClient(create_app(new_target.render_as_string(hide_password=False), TEST_SECRET)) as client:
            assert client.get("/schedules/1/entries", headers=login(client, "coordinator")).status_code == 200
    finally:
        restored.dispose()
        Path(new_file).unlink(missing_ok=True)

