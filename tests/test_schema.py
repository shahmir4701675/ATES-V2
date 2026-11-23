"""Rehearse the catalog baseline and Phase 1 runtime rights on disposable PostgreSQL."""

import json
import os
import re
import shutil
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from backend.api.app import create_app
from backend.cli import bootstrap
from backend.data.backups import backup, restore
from backend.data.database import ROOT, database
from backend.data.migrate import migrate
from backend.data.privileges import grant_local_runtime
from backend.data.store import Store
from backend.worker import run_once
from conftest import TEST_PASSWORD, TEST_SECRET
from test_master import login
from test_timetable import seed


def normalize_constraint(definition):
    # PostgreSQL deparses the same varchar array with a cast on the array
    # or with the cast distributed to each literal.
    return re.sub(r"\(ARRAY\[(.*?)\]\)::text\[\]", lambda match: "ARRAY[" + ", ".join(
        f"({item})::text" for item in match.group(1).split(", ")
    ) + "]", definition)


def test_DB_3_DB_4_DB_5_sqlite_constraints(migrated_db):
    with migrated_db.begin() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() >= "0002"
        for statement in (
            "INSERT INTO instructors (department_id, full_name, email) VALUES (1000, 'Test', 'test@example.test')",
            "INSERT INTO academic_terms (name, start_date, end_date) VALUES ('Invalid', '2026-11-21', '2026-11-20')",
        ):
            with pytest.raises(DBAPIError):
                connection.exec_driver_sql(statement)
        connection.exec_driver_sql("INSERT INTO audit_logs (action) VALUES ('test')")
        with pytest.raises(DBAPIError):
            connection.exec_driver_sql("DELETE FROM audit_logs")
        with pytest.raises(DBAPIError):
            connection.exec_driver_sql("UPDATE audit_logs SET action = 'changed'")


def test_DB_3_DB_5_DB_7_DB_9_SEC_8_postgres_catalog_and_runtime(postgres_db, tmp_path):
    original = json.loads((ROOT / "docs" / "SUPABASE_CATALOG.json").read_text(encoding="utf-8"))
    assert not inspect(postgres_db).get_table_names(), "Provide a fresh, empty disposable database."
    migrate(postgres_db, "0001")
    with postgres_db.connect() as connection:
        table_names = set(inspect(connection).get_table_names()) - {"alembic_version"}
        assert table_names == {table["name"].split(".")[1] for table in original["tables"]}
        for table in original["tables"]:
            name = table["name"].split(".")[1]
            constraints = connection.scalars(text("""
                SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = to_regclass(:name)
            """), {"name": name}).all()
            assert sorted(constraints) == sorted(map(normalize_constraint, table["constraints"])), name
            columns = connection.execute(text("""
                SELECT a.attname, a.attnotnull, a.attidentity, pg_get_expr(d.adbin,d.adrelid)
                FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE a.attrelid = to_regclass(:name) AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum
            """), {"name": name}).all()
            requested_columns = [line.split(None, 1)[0] for line in table["columns"]]
            assert [row[0] for row in columns] == requested_columns, name
            for line, (_, not_null, identity, default) in zip(table["columns"], columns):
                assert not_null == ("!" in line.partition("=")[0]), (name, line)
                assert bool(identity) == line.endswith("IDENTITY"), (name, line)
                assert default == (line.partition("=")[2] or None), (name, line)
            index_keys = connection.scalars(text("""
                SELECT substring(pg_get_indexdef(indexrelid) from ' USING btree (.*)$')
                FROM pg_index WHERE indrelid = to_regclass(:name)
            """), {"name": name}).all()
            assert sorted(index_keys) == sorted(table["index_keys_and_predicates"]), name
            triggers = connection.scalars(text("""
                SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid = to_regclass(:name) AND NOT tgisinternal
            """), {"name": name}).all()
            assert sorted(triggers) == sorted(table["enabled_user_triggers"]), name
            assert connection.scalar(text("""
                SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass(:name)
            """), {"name": name}) is True
        for function in original["public_functions"]:
            definition = connection.execute(text("""
                SELECT prosrc, prosecdef FROM pg_proc
                WHERE pronamespace = 'public'::regnamespace AND proname = :name
            """), {"name": function["name"]}).one()
            assert definition[0].strip() == function["definition"].strip()
            assert definition[1] is function["security_definer"]

    migrate(postgres_db)
    url = postgres_db.url.render_as_string(hide_password=False)
    bootstrap(url, "schema_admin", "Gate Administrator", "schema@example.test", TEST_PASSWORD)
    role = "ates_test_api_" + uuid4().hex[:12]
    role_password = uuid4().hex
    with postgres_db.begin() as connection:
        # The role and password are exclusively generated hexadecimal test values.
        connection.exec_driver_sql(f"CREATE ROLE {role} LOGIN PASSWORD '{role_password}' NOSUPERUSER NOBYPASSRLS")
        connection.exec_driver_sql("""
            INSERT INTO academic_terms (name, start_date, end_date) VALUES ('Test', '2026-11-21', '2026-12-20')
        """)
        connection.exec_driver_sql("""
            INSERT INTO scheduling_configs (term_id, schedule_type, name, created_by)
            SELECT term_id, 'Timetable', 'Test', (SELECT user_id FROM users LIMIT 1) FROM academic_terms
        """)
        connection.exec_driver_sql("SELECT fn_seed_default_constraint_rules(config_id) FROM scheduling_configs")
        connection.exec_driver_sql("SELECT fn_seed_default_constraint_rules(config_id) FROM scheduling_configs")
        rules = connection.exec_driver_sql("SELECT rule_code, weight, param_value FROM constraint_rules").all()
        assert len(rules) == 16 and ("S03", 5, 5) in rules
    grant_local_runtime(postgres_db, role)
    runtime = database(postgres_db.url.set(username=role, password=role_password))
    try:
        for malicious_statement in ("TRUNCATE audit_logs", "DELETE FROM audit_logs", "UPDATE audit_logs SET action = 'x'",
                                    "DELETE FROM users", "SELECT * FROM academic_terms"):
            with runtime.begin() as connection, pytest.raises(DBAPIError):
                connection.exec_driver_sql(malicious_statement)
        with TestClient(create_app(runtime.url.render_as_string(hide_password=False), TEST_SECRET)) as client:
            response = client.post("/auth/login", json={"username": "schema_admin", "password": TEST_PASSWORD})
            assert response.status_code == 200
            headers = {"Authorization": "Bearer " + response.json()["access_token"]}
            assert client.get("/api/users", headers=headers).status_code == 200
    finally:
        runtime.dispose()

    grant_local_runtime(postgres_db, role, "api")
    worker_role = role.replace("_api_", "_worker_")
    with postgres_db.begin() as connection:
        connection.exec_driver_sql(f"CREATE ROLE {worker_role} LOGIN PASSWORD '{role_password}' NOSUPERUSER NOBYPASSRLS")
    grant_local_runtime(postgres_db, worker_role, "worker")
    api_url = postgres_db.url.set(username=role, password=role_password).render_as_string(hide_password=False)
    worker_url = postgres_db.url.set(username=worker_role, password=role_password).render_as_string(hide_password=False)
    term_id, _ = seed(api_url, admin_username="schema_admin", initialize=False)
    worker = Store(worker_url)
    try:
        with TestClient(create_app(api_url, TEST_SECRET)) as client:
            coordinator = login(client, "coordinator")
            schedule = client.post("/schedules/generate", headers=coordinator, json={
                "term_id": term_id, "request_token": str(uuid4()),
            })
            assert schedule.status_code == 202, schedule.text
            key = schedule.json()["schedule_id"]
            assert run_once(worker, Event())
            assert client.get(f"/schedules/{key}/status", headers=coordinator).json()["status"] == "Generated"
            assert len(client.get(f"/schedules/{key}/entries", headers=coordinator).json()["entries"]) == 2
            for date in ("2027-03-01", "2027-03-02"):
                slot = client.post(f"/terms/{term_id}/exam-slots", headers=coordinator, json={
                    "exam_date": date, "start_time": "09:00", "end_time": "11:00",
                })
                assert slot.status_code == 201, slot.text
            exam = client.post("/schedules/generate", headers=coordinator, json={
                "term_id": term_id, "schedule_type": "Exam", "request_token": str(uuid4()),
            })
            assert exam.status_code == 202, exam.text
            key = exam.json()["schedule_id"]
            assert run_once(worker, Event())
            assert client.get(f"/schedules/{key}/status", headers=coordinator).json()["status"] == "Generated"
            assert len(client.get(f"/schedules/{key}/entries", headers=coordinator).json()["entries"]) == 2
    finally:
        worker.engine.dispose()

    if os.getenv("ATES_PG_BIN") or (shutil.which("pg_dump") and shutil.which("pg_restore")):
        source = backup(postgres_db.url, tmp_path)
        target = "ates_disposable_restore_" + uuid4().hex
        with postgres_db.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f"CREATE DATABASE {target}")
        target_url = postgres_db.url.set(database=target)
        restore(target_url, source)
        recovered = database(target_url)
        try:
            tables = ("academic_terms", "schedules", "schedule_runs", "timetable_entries", "exam_entries",
                      "exam_room_allocations", "scheduling_configs", "constraint_rules", "audit_logs", "alembic_version")
            with postgres_db.connect() as original, recovered.connect() as copy:
                for table in tables:
                    query = f"SELECT * FROM {table} ORDER BY 1"
                    assert original.exec_driver_sql(query).all() == copy.exec_driver_sql(query).all()
        finally:
            recovered.dispose()
        print("PostgreSQL backup restored into a fresh database and matched ten tables.")

