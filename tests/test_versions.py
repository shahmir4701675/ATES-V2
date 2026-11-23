"""Phase 6 verification for guarded edits and publication."""

from threading import Event
from time import perf_counter
from uuid import uuid4
import os
import sys

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from backend.api.app import create_app
from backend.cli import LOCAL
from backend.data.store import Store
from backend.worker import run_once
from conftest import TEST_SECRET
from test_browser import browser_sign_in, running_server
from test_master import login, new_user
from test_timetable import seed


def prepare(url):
    term, _ = seed(url)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        admin = login(client, "admin")
        new_user(client, admin, "approver", "Approver")
        new_user(client, admin, "faculty", "Faculty", instructor_id=2)
        new_user(client, admin, "student", "Student", batch_id=1)
        coordinator = login(client, "coordinator")
        response = client.post("/rooms", headers=coordinator, json={
            "room_code": "R102", "building": "Main", "capacity": 30, "room_type": "Lecture",
        })
        assert response.status_code == 201
    return term


def generate(client, coordinator, store, term, source=None):
    result = client.post("/schedules/generate", headers=coordinator, json={
        "term_id": term, "request_token": str(uuid4()), "source_id": source,
    })
    assert result.status_code == 202, result.text
    assert run_once(store, Event())
    key = result.json()["schedule_id"]
    assert client.get(f"/schedules/{key}/status", headers=coordinator).json()["status"] == "Generated"
    return key


def test_FR_6_10_FR_8_3_8_7_FR_9_2_9_5_stale_edit_and_publication(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    term = prepare(url)
    store = Store(url)
    try:
        with TestClient(create_app(url, TEST_SECRET)) as client:
            coord = login(client, "coordinator")
            approval = login(client, "approver")
            faculty = login(client, "faculty")
            student = login(client, "student")
            first = generate(client, coord, store, term)
            entries_url = f"/schedules/{first}/entries"
            fields = {"revision": 1, "entry": "1:Lecture:1", "slot_id": 2}
            started = perf_counter()
            invalid = client.put(entries_url, headers=coord, json=fields)
            elapsed = perf_counter() - started
            assert invalid.status_code == 409 and "H07" in invalid.json()["detail"]["message"]
            print(f"P-4 local SQLite rejected move latency {elapsed:.3f} seconds")
            assert elapsed <= 1
            assert client.get(entries_url, headers=faculty).status_code == 404
            moved = client.put(entries_url, headers=coord, json={**fields, "slot_id": 1, "room_id": 3})
            assert moved.status_code == 200
            assert client.get(entries_url, headers=coord).json()["entries"][0]["is_manual_override"] is True
            assert client.put(entries_url, headers=coord, json={**fields, "slot_id": 1}).status_code == 409
            lock_url = f"/schedules/{first}/locks"
            locked = client.put(lock_url, headers=coord, json={
                "revision": moved.json()["revision"], "entry": fields["entry"], "locked": True,
            })
            assert locked.status_code == 200
            rerun = generate(client, coord, store, term, source=first)
            pinned = client.get(f"/schedules/{rerun}/entries", headers=coord).json()["entries"][0]
            assert pinned["room"] == 3 and pinned["slots"] == [1] and pinned["is_locked"] is True
            unlocked = client.put(lock_url, headers=coord, json={
                "revision": locked.json()["revision"], "entry": fields["entry"], "locked": False,
            })
            assert unlocked.status_code == 200
            restored = client.post(f"/schedules/{first}/undo", headers=coord, json=unlocked.json())
            assert restored.status_code == 200
            assert client.get(entries_url, headers=coord).json()["entries"][0]["room"] == 1
            publish_url = f"/schedules/{first}/publish"
            assert client.post(publish_url, headers=coord, json={**restored.json(), "confirmed": True}).status_code == 403
            assert client.post(publish_url, headers=approval, json={**restored.json(), "confirmed": True}).status_code == 200
            faculty_entries = client.get(entries_url, headers=faculty).json()["entries"]
            student_entries = client.get(entries_url, headers=student).json()["entries"]
            assert len(faculty_entries) == 1 and faculty_entries[0]["kind"] == "Lab"
            assert len(student_entries) == 2

            second = generate(client, coord, store, term)
            second_url = f"/schedules/{second}/publish"
            assert client.post(second_url, headers=approval, json={"revision": 1, "confirmed": True}).status_code == 409
            assert client.post(second_url, headers=approval, json={
                "revision": 1, "confirmed": True, "replace_id": first,
            }).status_code == 200
            assert client.get(entries_url, headers=student).status_code == 404
            assert client.get(entries_url, headers=coord).status_code == 200
            archived = client.get(f"/schedules/{first}/status", headers=coord).json()
            assert archived["status"] == "Archived"
            duplicate = client.post(f"/schedules/{first}/duplicate", headers=coord, json={"revision": archived["revision"]})
            assert duplicate.status_code == 201, duplicate.text
            draft_id = duplicate.json()["schedule_id"]
            ready = client.post(f"/schedules/{draft_id}/validate-draft", headers=coord, json={"revision": 1})
            assert ready.status_code == 200 and ready.json()["status"] == "Generated"
            closed = client.put(f"/terms/{term}", headers=coord, json={
                "name": "Spring", "start_date": "2027-01-01", "end_date": "2027-05-01",
                "status": "Closed", "confirm_close": True,
            })
            assert closed.status_code == 200
            assert client.get(f"/schedules/{second}/entries", headers=student).status_code == 404
    finally:
        store.engine.dispose()


def test_UC_13_UC_14_approver_and_published_reader_browser(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    term = prepare(url)
    store = Store(url)
    try:
        with TestClient(create_app(url, TEST_SECRET)) as client:
            generate(client, login(client, "coordinator"), store, term)
    finally:
        store.engine.dispose()
    artifacts = LOCAL / "evidence" / "phase6"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        coordinator = browser.new_context(ignore_https_errors=True, viewport={"width": 360, "height": 800})
        editor = coordinator.new_page()
        editor.goto(address)
        browser_sign_in(editor, "coordinator")
        editor.get_by_role("link", name="Timetables", exact=True).click()
        editor.get_by_role("link", name="Open version").click()
        editor.get_by_role("link", name="View timetable").click()
        editor.get_by_label("Teaching session").select_option(label="CS101 · Lecture · 1")
        editor.get_by_label("Destination start slot").select_option(label="Monday · 09:00")
        editor.get_by_role("button", name="Move entry").click()
        expect(editor.get_by_role("alert")).to_contain_text("H07")
        editor.get_by_label("Destination start slot").select_option(label="Monday · 08:00")
        editor.get_by_label("Destination room").select_option(label="R102")
        editor.get_by_role("button", name="Move entry").click()
        expect(editor.get_by_text("Entry moved.", exact=True)).to_be_visible()
        editor.reload()
        expect(editor.get_by_text("Manual override", exact=True)).to_be_visible()
        coordinator.close()
        approver = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800})
        page = approver.new_page()
        page.goto(address)
        browser_sign_in(page, "approver")
        page.get_by_role("link", name="Timetables", exact=True).click()
        page.get_by_role("link", name="Open version").click()
        expect(page.get_by_role("heading", name="Review and publish")).to_be_visible()
        page.get_by_text("Publish this schedule for Faculty and Students.", exact=True).click()
        page.get_by_role("button", name="Publish schedule").click()
        expect(page.get_by_text("Published", exact=True)).to_be_visible()
        page.screenshot(path=artifacts / "published-version.png", full_page=True)
        for name in ("faculty", "student"):
            context = browser.new_context(ignore_https_errors=True, viewport={"width": 360, "height": 800})
            reader = context.new_page()
            reader.goto(address)
            browser_sign_in(reader, name)
            reader.get_by_role("link", name="Published timetable").click()
            expect(reader.get_by_role("heading", name="Weekly timetable")).to_be_visible()
            expect(reader.get_by_text("CS102 · Lab", exact=True)).to_be_visible()
            expect(reader.get_by_text("CS101 · Lecture", exact=True)).to_have_count(0 if name == "faculty" else 1)
            assert reader.evaluate("document.documentElement.scrollWidth") == 360
            context.close()
        approver.close()
        browser.close()

def test_SAF_1_SAF_4_corrupt_candidate_and_concurrent_replacement(migrated_db):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import update

    url = migrated_db.url.render_as_string(hide_password=False)
    term = prepare(url)
    store = Store(url)
    try:
        with TestClient(create_app(url, TEST_SECRET)) as client:
            coord = login(client, "coordinator")
            first = generate(client, coord, store, term)
            approver = login(client, "approver")
            first_result = client.post(f"/schedules/{first}/publish", headers=approver, json={
                "revision": 1, "confirmed": True,
            })
            assert first_result.status_code == 200
            corrupt = generate(client, coord, store, term)
            assert not client.get(f"/schedules/{corrupt}/review", headers=approver).json()["issues"]
            entries = store["timetable_entries"]
            with store.transaction() as connection:
                connection.execute(update(entries).where(
                    entries.c.schedule_id == corrupt, entries.c.session_type == "Lecture",
                ).values(slot_id=2))
            refused = client.post(f"/schedules/{corrupt}/publish", headers=approver, json={
                "revision": 1, "confirmed": True, "replace_id": first,
            })
            assert refused.status_code == 422 and "H07" in refused.json()["detail"]["message"]
            next_versions = [generate(client, coord, store, term) for _ in range(2)]
            accounts = [login(client, "approver"), login(client, "approver")]

            def publish(candidate):
                key, headers = candidate
                return client.post(f"/schedules/{key}/publish", headers=headers, json={
                    "revision": 1, "confirmed": True, "replace_id": first,
                }).status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(publish, zip(next_versions, accounts)))
            assert sorted(statuses) == [200, 409]
            listed = client.get(f"/schedules?term_id={term}", headers=coord).json()
            assert sum(row["status"] == "Published" for row in listed) == 1
            assert client.get(f"/schedules/{first}/status", headers=coord).json()["status"] == "Archived"
    finally:
        store.engine.dispose()


