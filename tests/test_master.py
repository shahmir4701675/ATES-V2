"""Phase 2 API and browser gates, including stable slot IDs and scoped availability."""

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import MetaData, select
import os
import sys

from backend.api.app import create_app
from backend.cli import LOCAL, bootstrap
from backend.services.master import demand
from conftest import TEST_PASSWORD, TEST_SECRET
from test_browser import browser_sign_in, running_server


def login(client, name):
    response = client.post("/auth/login", json={"username": name, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def new_user(client, admin, name, role, **links):
    response = client.post("/api/users", headers=admin, json={
        "username": name, "email": name + "@example.test", "full_name": name.title(), "role": role,
        "password": TEST_PASSWORD, **links,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_FR_2_6_2_7_2_9_FR_3_1_3_3_idempotency_and_defaults(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    bootstrap(url, "admin", "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        admin = login(client, "admin")
        new_user(client, admin, "coordinator", "Coordinator")
        new_user(client, admin, "approver", "Approver")
        coord = login(client, "coordinator")
        approver = login(client, "approver")
        term_form = {"name": "Spring", "start_date": "2027-01-01", "end_date": "2027-05-01", "status": "Active"}
        assert client.post("/terms", headers=approver, json=term_form).status_code == 403
        term_id = client.post("/terms", headers=coord, json=term_form).json()["term_id"]
        grid_path = f"/terms/{term_id}/grid"
        grid = {"days": [1, 2], "first_start": "08:00", "slot_minutes": 30, "slots_per_day": 3}
        first = client.put(grid_path, headers=coord, json=grid).json()
        assert len(first) == 6
        slot_id = first[-1]["slot_id"]
        assert client.put(f"/slots/{slot_id}/block", headers=coord, json={"is_blocked": True}).status_code == 422
        assert client.put(f"/slots/{slot_id}/block", headers=coord,
                          json={"is_blocked": True, "block_reason": "Prayer"}).status_code == 204
        assert client.put(grid_path, headers=coord, json={**grid, "days": [1]}).status_code == 409
        second = client.put(grid_path, headers=coord, json=grid).json()
        assert [row["slot_id"] for row in second] == [row["slot_id"] for row in first]
        assert second[-1]["block_reason"] == "Prayer"
        assert client.get(grid_path, headers=approver).json() == second
        faculty = new_user(client, admin, "faculty", "Faculty", instructor={
            "full_name": "Gate Instructor", "email": "gate@example.test",
            "department": {"name": "Computer Science", "code": "CS"},
        })
        faculty_headers = login(client, "faculty")
        instructor_id = faculty["instructor_id"]
        available_url = f"/availability/{term_id}"
        assert all(row["is_available"] for row in client.get(available_url, headers=faculty_headers).json())
        assert client.put(f"/availability/slots/{slot_id}", headers=faculty_headers,
                          params={"instructor_id": instructor_id + 1}, json={"is_available": False}).status_code == 403
        assert client.put(f"/availability/slots/{slot_id}", headers=faculty_headers,
                          json={"is_available": False}).status_code == 204
        assert client.put(grid_path, headers=coord, json=grid).status_code == 200
        assert client.get(available_url, headers=faculty_headers).json()[-1]["is_available"] is False
        switched = client.post("/terms", headers=coord, json={**term_form, "name": "Autumn"}).json()["term_id"]
        assert client.get("/api/dashboard", headers=coord).json()["active_term"]["term_id"] == switched
    assert demand({"lecture_hours": 2, "lab_hours": 1}, 60) == {"lecture_slots": 2, "lab_slots": 1}
    assert demand({"lecture_hours": 2, "lab_hours": 1}, 30) == {"lecture_slots": 4, "lab_slots": 2}
    metadata = MetaData()
    metadata.reflect(migrated_db)
    with migrated_db.connect() as connection:
        assert len(connection.execute(select(metadata.tables["constraint_rules"])).all()) == 48


def create(page, section, name, fields, selections=None, invalid=False):
    page.get_by_role("link", name=section, exact=True).click()
    page.get_by_role("button", name=f"Add {name}", exact=True).click()
    for label, value in fields.items():
        page.get_by_label(label, exact=True).fill(value)
    for label, value in (selections or {}).items():
        page.get_by_label(label, exact=True).select_option(label=value)
    page.get_by_role("button", name=f"Create {name}", exact=True).click()
    if invalid:
        expect(page.get_by_role("alert")).to_be_visible()
    else:
        expect(page.get_by_role("status").filter(has_text="Record saved.")).to_be_visible()


def test_UC_04_UC_17_coordinator_and_faculty_setup_browser(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    bootstrap(url, "admin", "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        admin = login(client, "admin")
        new_user(client, admin, "coordinator", "Coordinator")
    artifacts = LOCAL / "evidence" / "phase2"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(address)
        browser_sign_in(page, "coordinator")
        page.get_by_role("link", name="Set up the active term").click()
        create(page, "Terms", "term", {
            "Term name": "Spring 2027", "Start date": "2027-01-01", "End date": "2027-05-01",
        }, {"Status": "Active"})
        page.get_by_role("link", name="Weekly grid").click()
        for day in ("Wednesday", "Thursday", "Friday", "Saturday"):
            page.get_by_label(day, exact=True).uncheck()
        page.get_by_label("Slots per day").fill("3")
        page.get_by_role("button", name="Save weekly grid").click()
        expect(page.get_by_role("article")).to_have_count(6)
        page.get_by_role("button", name="Save weekly grid").click()
        expect(page.get_by_role("article")).to_have_count(6)
        page.reload()
        expect(page.get_by_role("article")).to_have_count(6)
        page.get_by_role("article", name="Monday 09:00").get_by_role("button", name="Block slot").click()
        page.get_by_label("Block reason").fill("Break")
        page.get_by_role("button", name="Save slot").click()
        expect(page.get_by_text("Blocked · Break")).to_be_visible()
        create(page, "Departments", "department", {"Department code": "CS", "Department name": "Computing"})
        create(page, "Instructors", "instructor", {"Instructor name": "Gate Teacher", "Email": "teacher@example.test"},
               {"Department": "Computing"})
        create(page, "Batches", "batch", {"Programme code": "CS", "Year": "2026", "Section": "A", "Student count": "25"},
               {"Department": "Computing"})
        create(page, "Rooms", "room", {"Room code": "R101", "Building": "Main", "Capacity": "30"})
        for course in ("CS101", "CS102"):
            create(page, "Courses", "course", {"Course code": course, "Course title": course + " Title",
                   "Credit hours": "1", "Weekly lecture hours": "1"}, {"Department": "Computing"})
            create(page, "Offerings", "offering", {"Enrolled count": "25"}, {
                "Course": f"{course} · {course} Title", "Instructor": "Gate Teacher", "Batch": "CS 2026 A",
            })
        page.set_viewport_size({"width": 360, "height": 800})
        create(page, "Offerings", "offering", {"Enrolled count": "25"}, {
            "Course": "CS102 · CS102 Title", "Instructor": "Gate Teacher", "Batch": "CS 2026 A",
        }, invalid=True)
        expect(page.get_by_label("Course", exact=True)).to_have_value("2")
        page.get_by_role("button", name="Cancel", exact=True).click()
        expect(page.get_by_role("article")).to_have_count(2)
        assert page.evaluate("document.documentElement.scrollWidth") == 360
        page.screenshot(path=artifacts / "offerings-mobile.png", full_page=True)

        with TestClient(create_app(url, TEST_SECRET)) as client:
            new_user(client, login(client, "admin"), "faculty", "Faculty", instructor_id=1)

        page.get_by_role("button", name="Sign out").click()
        browser_sign_in(page, "faculty")
        page.get_by_role("link", name="Availability").click()
        slot = page.get_by_role("article", name="Tuesday 08:00")
        slot.get_by_role("button", name="Mark unavailable").click()
        expect(page.get_by_text("Regenerate any existing draft", exact=False)).to_be_visible()
        page.reload()
        expect(slot.get_by_role("button", name="Mark available")).to_be_visible()
        context.close()
        browser.close()

