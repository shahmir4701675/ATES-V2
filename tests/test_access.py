"""FR-1.1 through FR-1.8, SEC-1 through SEC-4 and SEC-9."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, select

from backend.api.app import create_app
from backend.cli import bootstrap
from conftest import TEST_PASSWORD, TEST_SECRET


def test_FR_1_1_to_1_4_and_SEC_9_sessions_lockout_and_audit(migrated_db):
    now = datetime(2026, 11, 21, 12)
    url = migrated_db.url.render_as_string(hide_password=False)
    bootstrap(url, "admin", "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    with TestClient(create_app(url, TEST_SECRET, lambda: now)) as client:
        def login(password=TEST_PASSWORD, username="admin"):
            return client.post("/auth/login", json={"username": username, "password": password})

        assert client.get("/openapi.json").status_code == 401
        assert login(username="unknown").status_code == 401
        for _ in range(4):
            assert login("incorrect").status_code == 401
        offer = login()
        assert offer.status_code == 200
        first = {"Authorization": "Bearer " + offer.json()["access_token"]}
        for _ in range(4):
            assert login("incorrect").status_code == 401
        locked = login("incorrect")
        assert locked.status_code == 423
        assert locked.json()["detail"]["retry_minutes"] == 15
        assert client.get("/auth/session", headers=first).status_code == 401
        now += timedelta(minutes=14, seconds=1)
        assert login().json()["detail"]["retry_minutes"] == 1
        now += timedelta(seconds=59)
        second = {"Authorization": "Bearer " + login().json()["access_token"]}
        now += timedelta(minutes=29)
        assert client.get("/auth/session", headers=second).status_code == 200
        now += timedelta(minutes=30)
        assert client.get("/auth/session", headers=second).status_code == 401

        fresh = {"Authorization": "Bearer " + login().json()["access_token"]}
        assert client.post("/auth/logout", headers=fresh).status_code == 204
        assert client.get("/api/dashboard", headers=fresh).status_code == 401
        fresh = {"Authorization": "Bearer " + login().json()["access_token"]}
        changed = client.put("/auth/password", headers=fresh, json={"current_password": TEST_PASSWORD, "password": "12345678"})
        assert changed.status_code == 204
        assert client.get("/auth/session", headers=fresh).status_code == 401
        assert login().status_code == 401
        assert login("12345678").status_code == 200

    metadata = MetaData()
    metadata.reflect(migrated_db)
    logs = metadata.tables["audit_logs"]
    with migrated_db.connect() as connection:
        rows = connection.execute(select(logs)).mappings().all()
        assert any(row["action"] == "login_failed" and row["user_id"] is None for row in rows)
        assert {"account_locked", "logout", "password_changed"} <= {row["action"] for row in rows}
        assert all(TEST_PASSWORD not in (row["details"] or "") for row in rows)


def test_FR_1_2_1_5_1_6_1_7_bcrypt_role_changes_and_retention(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    bootstrap(url, "admin", "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        def login(username, password=TEST_PASSWORD):
            result = client.post("/auth/login", json={"username": username, "password": password})
            assert result.status_code == 200
            assert "password_hash" not in result.json()["user"]
            return {"Authorization": "Bearer " + result.json()["access_token"]}

        admin = login("admin")
        assert client.get("/openapi.json", headers=admin).status_code == 200
        plain = {"username": "coord", "email": "coord@example.test", "full_name": "ثناء",
                 "role": "Coordinator", "password": "1234567"}
        short = client.post("/api/users", headers=admin, json=plain)
        assert short.status_code == 422 and "password" in short.json()["detail"]["fields"]
        pending = client.post("/api/users", headers=admin, json={**plain, "password": TEST_PASSWORD})
        assert pending.status_code == 201 and pending.json()["full_name"] == "ثناء"
        user_id = pending.json()["user_id"]
        coordinator = login("coord")
        assert client.get("/api/users", headers=coordinator).status_code == 403
        assert client.get("/openapi.json", headers=coordinator).status_code == 403
        assert client.put(f"/api/users/{user_id}/status", headers=coordinator, json={"active": False}).status_code == 403

        replaced = {**plain, "role": "Approver"}
        del replaced["password"]
        assert client.put(f"/api/users/{user_id}", headers=admin, json=replaced).status_code == 200
        assert client.get("/auth/session", headers=coordinator).status_code == 401
        approver = login("coord")
        assert client.get("/api/dashboard", headers=approver).json()["user"]["role"] == "Approver"
        assert client.put(f"/api/users/{user_id}/status", headers=admin, json={"active": False}).status_code == 204
        assert client.get("/auth/session", headers=approver).status_code == 401
        assert client.delete(f"/api/users/{user_id}", headers=admin).status_code == 405
        assert client.get("/api/users?search=coord", headers=admin).json()["items"][0]["account_status"] == "Deactivated"
        assert client.put(f"/api/users/{user_id}/status", headers=admin, json={"active": True}).status_code == 204

    metadata = MetaData()
    metadata.reflect(migrated_db)
    with migrated_db.connect() as connection:
        hashes = connection.scalars(select(metadata.tables["users"].c.password_hash)).all()
        assert len(set(hashes)) == 2 and all(value.startswith("$2b$12$") for value in hashes)
        logs = metadata.tables["audit_logs"]
        assert connection.scalar(select(logs.c.user_id).where(logs.c.action == "login_success", logs.c.user_id == user_id)) == user_id

