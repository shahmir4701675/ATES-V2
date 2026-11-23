"""Phase 4 CSV staging, settings, timing and browser route checks."""

from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, func, select

from backend.api.app import create_app
from backend.cli import bootstrap
from backend.services.csv_output import csv_text
from backend.services.imports import CsvTypes, MB_10
from conftest import TEST_PASSWORD, TEST_SECRET
from test_master import login, new_user


def test_FR_4_1_4_5_FR_5_1_5_8_csv_and_settings(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    bootstrap(url, "admin", "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        admin = login(client, "admin")
        new_user(client, admin, "coordinator", "Coordinator")
        coord = login(client, "coordinator")

        def post(path, **body):
            reply = client.post(path, headers=coord, json=body)
            assert reply.status_code == 201, reply.text
            return reply.json()

        term = post("/terms", name="Spring 2027", start_date="2027-01-01", end_date="2027-05-01", status="Active")
        term_id = term["term_id"]
        post("/departments", name="Computing", code="CS")
        configs = client.get("/configs", params={"term_id": term_id}, headers=coord).json()
        assert {row["schedule_type"] for row in configs} == {"Timetable", "Exam"}
        protected = set()
        for config in configs:
            rules_url = f"/configs/{config['config_id']}/rules"
            rules = client.get(rules_url, headers=coord).json()
            assert len(rules) == (16 if config["schedule_type"] == "Timetable" else 8)
            for rule in rules:
                code = rule["rule_code"]
                if code in {"H01", "H02", "H03", "H08", "E01", "E04", "E05"}:
                    form = {key: rule[key] for key in ("rule_code", "weight", "param_value")}
                    response = client.put(rules_url, headers=coord, json={
                        "confirmed_disable": True, "rules": [{**form, "is_enabled": False}],
                    })
                    assert response.status_code == 422
                    protected.add(code)
            if config["schedule_type"] == "Timetable":
                planned = {"rules": [{"rule_code": "H04", "is_enabled": False, "weight": 0},
                                     {"rule_code": "S01", "is_enabled": True, "weight": 0},
                                     {"rule_code": "S06", "is_enabled": True, "weight": 10}]}
                assert client.put(rules_url, headers=coord, json=planned).status_code == 409
                assert client.put(rules_url, headers=coord, json={**planned, "confirmed_disable": True}).status_code == 200
                clone = post("/configs", term_id=term_id, schedule_type="Timetable", name="Clone", clone_id=config["config_id"])
                assert client.delete(f"/configs/{clone['config_id']}", headers=coord).status_code == 204
        assert len(protected) == 7

        sessions_url = f"/terms/{term_id}/exam-slots"
        post(sessions_url, exam_date="2027-04-01", start_time="09:00", end_time="11:00", label="Morning")
        overlap = client.post(sessions_url, headers=coord, json={
            "exam_date": "2027-04-01", "start_time": "10:45", "end_time": "12:00",
        })
        assert overlap.status_code == 409
        post(sessions_url, exam_date="2027-04-01", start_time="11:00", end_time="12:00")

        def preview(entity, content, key=None, filename=None):
            return client.post(f"/import/{entity}", headers=coord, data={"request_token": key or str(uuid4())},
                files={"file": (filename or entity + ".csv", content, "text/csv")})

        def complete(key, action="confirm"):
            response = client.post(f"/import/previews/{key}/{action}", headers=coord)
            assert response.status_code == 200, response.text
            return response.json()

        for entity in CsvTypes:
            template = client.get(f"/import/templates/{entity}", headers=coord)
            assert template.status_code == 200 and template.headers["content-type"].startswith("text/csv")
            content = template.content
            if entity == "courses":
                content = content.decode().replace("Introduction to Computing", "کمپیوٹنگ").encode()
                content += b"BAD,Bad,UNKNOWN,3,3,0\r\n"
            if entity == "enrollments":
                batch_id = client.get("/batches", headers=coord).json()["items"][0]["batch_id"]
                new_user(client, admin, "student1", "Student", batch_id=batch_id)
            key = str(uuid4())
            first = preview(entity, content, key)
            assert first.status_code == 200, first.text
            batch = first.json()
            assert batch["valid_count"] == 1
            assert preview(entity, content, key).json() == batch
            assert client.get(f"/{entity}", headers=coord).json()["total"] == 0
            if entity == "courses":
                assert batch["rejected"][0]["line"] == 3
                assert batch["rejected"][0]["issues"][0]["column"] == "department_code"
            assert complete(key)["state"] == "Confirmed"
            assert complete(key)["state"] == "Confirmed"
            assert client.get(f"/{entity}", headers=coord).json()["total"] == 1

        assert preview("rooms", b"a" * (MB_10 + 1)).status_code == 413
        assert preview("rooms", b"not CSV", filename="rooms.txt").status_code == 422
        header = list(CsvTypes["rooms"][1])
        template = csv_text([header, ["ABANDONED", "Main", 15, "Lecture"]]).encode()
        cancelled = preview("rooms", template).json()
        assert complete(cancelled["key"], "cancel")["state"] == "Cancelled"
        assert complete(cancelled["key"])["state"] == "Cancelled"
        assert client.get("/rooms", headers=coord).json()["total"] == 1

        large = csv_text([header, *([f"ROOM{index}", "Main", 35, "Lecture"] for index in range(5000))]).encode()
        started = perf_counter()
        uploaded = preview("rooms", large).json()
        assert uploaded["valid_count"] == 5000
        assert complete(uploaded["key"])["state"] == "Confirmed"
        elapsed = perf_counter() - started
        print(f"P-5: 5,000-row local SQLite preview plus commit {elapsed:.3f} seconds")
        assert client.get("/rooms", headers=coord).json()["total"] == 5001

    metadata = MetaData()
    metadata.reflect(migrated_db)
    with migrated_db.connect() as connection:
        logs = metadata.tables["import_logs"]
        assert connection.scalar(select(func.count()).select_from(logs)) == 7

def test_UC_05_mixed_import_to_generation_browser(migrated_db):
    import os
    import sys
    from playwright.sync_api import expect, sync_playwright

    from backend.cli import LOCAL
    from test_browser import browser_sign_in, running_server
    from test_timetable import seed

    url = migrated_db.url.render_as_string(hide_password=False)
    seed(url)
    artifacts = LOCAL / "evidence" / "phase4"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts, worker=True) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 360, "height": 800})
        page = context.new_page()
        page.goto(address)
        browser_sign_in(page, "coordinator")
        page.get_by_role("link", name="Import CSV").click()
        page.get_by_label("Import type").select_option(label="Rooms")
        with page.expect_download() as template:
            page.get_by_role("button", name="Download template").click()
        assert template.value.suggested_filename == "rooms.csv"
        page.get_by_label("CSV file").set_input_files({
            "name": "mixed.csv", "mimeType": "text/csv",
            "buffer": b"room_code,building,capacity,room_type\nR200,Main,30,Lecture\nBAD,Main,0,Lab\n",
        })
        page.get_by_role("button", name="Preview import").click()
        expect(page.get_by_text("Line 3", exact=True)).to_be_visible()
        page.screenshot(path=artifacts / "import-preview.png", full_page=True)
        page.get_by_role("button", name="Import valid rows").click()
        expect(page.get_by_text("1 record(s) imported.", exact=True)).to_be_visible()
        page.get_by_role("link", name="Dashboard").click()
        page.get_by_role("link", name="Generate timetable").click()
        page.get_by_role("button", name="Generate", exact=True).click()
        page.get_by_role("link", name="View timetable").click(timeout=40_000)
        expect(page.get_by_text("2 sessions", exact=True)).to_be_visible()
        context.close()
        browser.close()


