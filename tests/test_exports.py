"""FR-11.1–FR-11.5 and FR-12.1–FR-12.3 download and log evidence."""

import csv
from io import BytesIO, StringIO
import os
import sys
from time import perf_counter

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader

from backend.api.app import create_app
from backend.cli import LOCAL
from backend.data.store import Store
from conftest import TEST_SECRET
from test_browser import browser_sign_in, running_server
from test_master import login
from test_versions import generate, prepare


def prepare_published(url):
    term = prepare(url)
    store = Store(url)
    try:
        with TestClient(create_app(url, TEST_SECRET)) as client:
            coord = login(client, "coordinator")
            key = generate(client, coord, store, term)
            approver = login(client, "approver")
            status = client.post(f"/schedules/{key}/publish", headers=approver, json={"revision": 1, "confirmed": True})
            assert status.status_code == 200, status.text
            draft = generate(client, coord, store, term)
        return key, draft
    finally:
        store.engine.dispose()


def test_FR_11_1_11_5_FR_12_1_12_3_exports_match_view_and_audit(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    key, draft = prepare_published(url)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        coord = login(client, "coordinator")
        faculty = login(client, "faculty")
        admin = login(client, "admin")
        assert client.get(f"/schedules/{draft}/export?format=csv", headers=faculty).status_code == 404
        assert client.get(f"/schedules/{key}/export?format=pdf&group_by=batch", headers=faculty).status_code == 403
        assert client.get("/audit", headers=coord).status_code == 403
        view = client.get(f"/schedules/{key}/entries?room=2", headers=faculty).json()
        csv_result = client.get(f"/schedules/{key}/export?format=csv&room=2", headers=faculty)
        rows = list(csv.DictReader(StringIO(csv_result.text)))
        assert len(rows) == len(view["entries"]) == 1
        assert rows[0]["Course code"] == "CS102" and rows[0]["Start time"] == "08:00"
        assert rows[0]["End time"] == "10:00" and rows[0]["Session type"] == "Lab"
        started = perf_counter()
        pdf = client.get(f"/schedules/{key}/export?format=pdf&group_by=instructor", headers=coord)
        elapsed = perf_counter() - started
        print(f"P-6 local two-instructor PDF {elapsed:.3f} seconds")
        assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
        document = PdfReader(BytesIO(pdf.content))
        assert len(document.pages) == 2
        for page in document.pages:
            assert abs(float(page.mediabox.width) - 841.89) < .01
            assert abs(float(page.mediabox.height) - 595.28) < .01
            assert "Spring" in page.extract_text() and "Version 1" in page.extract_text()
        assert "CS102" not in document.pages[0].extract_text()
        assert "CS102" in document.pages[1].extract_text()
        logs = client.get("/audit?username=faculty&action=schedule_exported", headers=admin).json()
        assert logs["total"] == 1 and logs["items"][0]["entity_id"] == key
        assert logs["items"][0]["created_at"].endswith("+00:00")
        assert client.get("/audit?from_time=2099-01-01T11%3A00", headers=admin).json()["total"] == 0

        directory = LOCAL / "evidence" / "phase7"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "instructor-export.pdf").write_bytes(pdf.content)
        (directory / "faculty-export.csv").write_bytes(csv_result.content)


def test_UC_03_UC_16_exports_and_audit_browser(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    prepare_published(url)
    artifacts = LOCAL / "evidence" / "phase7"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        for username in ("coordinator", "approver", "faculty", "student", "admin"):
            context = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800})
            page = context.new_page()
            page.goto(address)
            browser_sign_in(page, username)
            if username in ("coordinator", "approver"):
                page.get_by_role("link", name="Timetables", exact=True).click()
                page.get_by_role("link", name="Open version").last.click()
                page.get_by_role("link", name="View timetable").click()
            else:
                page.get_by_role("link", name="Published timetable").click()
            page.get_by_label("Room", exact=True).select_option(label="LAB")
            expect(page.get_by_text("1 session", exact=True)).to_be_visible()
            for ext in ("CSV", "PDF"):
                with page.expect_download() as response:
                    page.get_by_role("button", name="Export " + ext, exact=True).click()
                saved = response.value.path().read_bytes()
                if ext == "CSV":
                    assert saved.count(b"CS102") == 1 and b"CS101" not in saved
                else:
                    contents = PdfReader(BytesIO(saved)).pages[0].extract_text()
                    assert "CS102" in contents and "CS101" not in contents
            if username == "admin":
                page.get_by_role("link", name="Audit log").click()
                page.get_by_label("Actor username").fill("faculty")
                page.get_by_label("Action code").fill("schedule_exported")
                page.get_by_role("button", name="Apply filters").click()
                expect(page.get_by_role("article", name="schedule_exported")).to_have_count(2)
                page.screenshot(path=artifacts / "audit-log.png", full_page=True)
            context.close()
        browser.close()

