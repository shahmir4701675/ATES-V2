"""Phase 3 checks for the actual worker, model, validator and browser."""

from datetime import timedelta
from threading import Event
from uuid import uuid4
import os
import sys

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
import pytest
from sqlalchemy import event, func, select

from backend.api.app import create_app
from backend.cli import LOCAL, bootstrap
from backend.data.store import Store
from backend.engine.timetable import solve
from backend.engine.timetable_data import Assignment, Result, Timetable
from backend.engine.validator import objective, validate
from backend.services.rules import RULE_DEFAULTS
from backend.services.security import utc_now
from backend.worker import claim, run_once
from conftest import TEST_SECRET, TEST_PASSWORD
from test_browser import browser_sign_in, running_server
from test_master import login, new_user


def forced_choice():
    slots = []
    for day in (1, 2):
        for index in range(1, 4):
            slots.append({"slot_id": len(slots) + 1, "day_of_week": day, "slot_index": index,
                          "start_time": f"{7+index:02}:00:00", "end_time": f"{8+index:02}:00:00",
                          "minutes": 60, "is_blocked": day == 1 and index == 2})
    return {
        "slots": slots,
        "rooms": [
            {"room_id": 1, "capacity": 25, "room_type": "Lecture"},
            {"room_id": 2, "capacity": 70, "room_type": "Lecture"},
            {"room_id": 3, "capacity": 25, "room_type": "Lab"},
            {"room_id": 4, "capacity": 10, "room_type": "Lecture"},
        ],
        "instructors": [{"instructor_id": key, "max_daily_hours": 3, "max_weekly_hours": 3} for key in (1, 2)],
        "offerings": [
            {"offering_id": 1, "instructor_id": 1, "batch_id": 1, "enrolled_count": 25, "lecture_slots": 1, "lab_slots": 0},
            {"offering_id": 2, "instructor_id": 2, "batch_id": 1, "enrolled_count": 25, "lecture_slots": 0, "lab_slots": 2},
        ],
        "unavailable": [[1, 3], [1, 4], [1, 5], [1, 6], [2, 6]],
        "rules": [{"rule_code": code, "rule_type": kind, "is_enabled": True, "weight": weight, "param_value": param}
                  for code, kind, weight, param in RULE_DEFAULTS["Timetable"]],
    }


def test_FR_6_3_6_4_6_9_real_engine_is_deterministic():
    problem = Timetable(forced_choice())
    first = solve(problem, 10, 1)
    second = solve(problem, 10, 1)
    assert first.status == "optimal"
    assert first == second
    assert first.assignments == (Assignment("1:Lecture:1", 1, (1,)), Assignment("2:Lab:1", 3, (4, 5)))
    assert validate(problem, first.assignments) == []
    assert objective(problem, first.assignments) == 0


@pytest.mark.parametrize(("code", "lecture", "lab"), [
    ("H01", (1, (4,)), (3, (4, 5))),
    ("H02", (3, (4,)), (3, (4, 5))),
    ("H03", (1, (4,)), (3, (4, 5))),
    ("H04", (4, (1,)), (3, (4, 5))),
    ("H05", (3, (1,)), (3, (4, 5))),
    ("H06", (1, (3,)), (3, (4, 5))),
    ("H07", (1, (2,)), (3, (4, 5))),
    ("H08", None, (3, (4, 5))),
    ("H09", (1, (1,)), (3, (4, 6))),
    ("H10", (1, (1,)), (3, (4, 5))),
])
def test_H01_H10_independent_negative_cases(code, lecture, lab):
    frozen = forced_choice()
    if code == "H01":
        frozen["offerings"][1]["instructor_id"] = 1
    if code == "H10":
        frozen["instructors"][1]["max_daily_hours"] = 1
        frozen["instructors"][1]["max_weekly_hours"] = 1
    assignments = [Assignment("2:Lab:1", *lab)]
    if lecture:
        assignments.append(Assignment("1:Lecture:1", *lecture))
    assert code in {item["code"] for item in validate(Timetable(frozen), assignments)}


@pytest.mark.parametrize(("code", "better", "worse"), [
    ("S01", (1, 2), (1, 3)),
    ("S02", (1, 4), (1, 2)),
    ("S03", (1, 4), (1, 2)),
    ("S04", (1, 3), (1, 2)),
    ("S05", (1, 2), (1, 3)),
])
def test_S01_S05_preference_comparisons(code, better, worse):
    frozen = forced_choice()
    frozen["offerings"] = [{**frozen["offerings"][0], "lecture_slots": 2}]
    frozen["previous"] = {"1:Lecture:2": {"room": 1, "slots": [2]}}
    for rule in frozen["rules"]:
        if rule["rule_type"] == "Soft":
            rule["is_enabled"] = rule["rule_code"] == code
            rule["param_value"] = 1 if rule["rule_code"] in {"S03", "S04"} else None
    problem = Timetable(frozen)

    def score(slots):
        return objective(problem, tuple(Assignment(f"1:Lecture:{index}", 1, (slot,))
                                        for index, slot in enumerate(slots, 1)))

    assert score(better) > score(worse)


def test_S06_room_fit_preference():
    problem = Timetable(forced_choice())
    assert objective(problem, [Assignment("1:Lecture:1", 1, (1,))]) > objective(
        problem, [Assignment("1:Lecture:1", 2, (1,))])


def seed(url, admin_username="admin", initialize=True):
    if initialize:
        bootstrap(url, admin_username, "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        new_user(client, login(client, admin_username), "coordinator", "Coordinator")
        coord = login(client, "coordinator")

        def add(path, **body):
            response = client.post(path, headers=coord, json=body)
            assert response.status_code == 201, response.text
            return response.json()

        term_id = add("/terms", name="Spring", start_date="2027-01-01", end_date="2027-05-01", status="Active")["term_id"]
        dept = add("/departments", code="CS", name="Computing")["department_id"]
        batch = add("/batches", department_id=dept, program_code="CS", batch_year=2026, section="A", strength=25)["batch_id"]
        one = add("/instructors", department_id=dept, full_name="Instructor One", email="one@example.test")["instructor_id"]
        two = add("/instructors", department_id=dept, full_name="Instructor Two", email="two@example.test")["instructor_id"]
        add("/rooms", room_code="R101", building="Main", capacity=25, room_type="Lecture")
        small_lab = add("/rooms", room_code="LAB", building="Main", capacity=25, room_type="Lab")["room_id"]
        for code, lecture, lab, instructor in (("CS101", 1, 0, one), ("CS102", 0, 2, two)):
            course = add("/courses", department_id=dept, course_code=code, title=code + " Title",
                         credit_hours=1, lecture_hours=lecture, lab_hours=lab)["course_id"]
            add("/offerings", term_id=term_id, course_id=course, batch_id=batch, instructor_id=instructor, enrolled_count=25)
        grid = client.put(f"/terms/{term_id}/grid", headers=coord, json={
            "days": [1, 2], "first_start": "08:00", "slots_per_day": 2,
        }).json()
        assert client.put(f"/slots/{grid[1]['slot_id']}/block", headers=coord, json={
            "is_blocked": True, "block_reason": "Break",
        }).status_code == 204
        for slot in grid[2:]:
            assert client.put(f"/availability/slots/{slot['slot_id']}", headers=coord,
                              params={"instructor_id": one}, json={"is_available": False}).status_code == 204
    return term_id, small_lab


def test_FR_6_1_6_6_6_7_DB_6_worker_outcomes_and_idempotency(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    term_id, room_id = seed(url)
    store = Store(url)
    try:
        with TestClient(create_app(url, TEST_SECRET)) as client:
            coord = login(client, "coordinator")

            def start(attempt=None):
                response = client.post("/schedules/generate", headers=coord, json={
                    "term_id": term_id, "request_token": attempt or str(uuid4()),
                })
                assert response.status_code in (201, 202), response.text
                return response.json()["schedule_id"]

            attempt = str(uuid4())
            first = start(attempt)
            assert start(attempt) == first

            result = client.get(f"/schedules/{first}/status", headers=coord)
            assert result.json()["phase"] == "Queued"
            assert run_once(store, Event())
            assert client.get(f"/schedules/{first}/status", headers=coord).json()["status"] == "Generated"
            entries = client.get(f"/schedules/{first}/entries", headers=coord).json()["entries"]
            assert [(row["key"], row["slots"]) for row in entries] == [("1:Lecture:1", [1]), ("2:Lab:1", [3, 4])]
            assert client.get(f"/schedules/{first}/conflicts", headers=coord).json() == []

            invalid = start()
            assert run_once(store, Event(), solver=lambda *_: Result("optimal"))
            assert client.get(f"/schedules/{invalid}/status", headers=coord).json()["solver_status"] == "interrupted"
            assert "validator rejected" in client.get(f"/schedules/{invalid}/status", headers=coord).json()["outcome"]

            failed_write = start()
            attempted = False

            def fail_result_status(connection, cursor, statement, parameters, context, executemany):
                nonlocal attempted
                if not attempted and statement.startswith("UPDATE schedules SET status="):
                    attempted = True
                    raise RuntimeError("Synthetic storage failure after inserting assignments")

            event.listen(store.engine, "before_cursor_execute", fail_result_status)
            try:
                assert run_once(store, Event()) and attempted
            finally:
                event.remove(store.engine, "before_cursor_execute", fail_result_status)
            outcome = client.get(f"/schedules/{failed_write}/status", headers=coord).json()
            assert outcome["status"] == "Infeasible" and "could not be saved" in outcome["outcome"]

            queued = start()
            assert client.post(f"/schedules/{queued}/cancel", headers=coord).json()["outcome"] == "Cancelled by coordinator."
            stale = start()
            assert claim(store)[0] == stale
            table = store["schedule_runs"]
            with store.transaction() as connection:
                connection.execute(table.update().where(table.c.schedule_id == stale)
                                   .values(heartbeat_at=utc_now() - timedelta(seconds=30)))
            assert not run_once(store, Event())
            assert client.get(f"/schedules/{stale}/status", headers=coord).json()["solver_status"] == "interrupted"

            assert client.put(f"/rooms/{room_id}", headers=coord, json={
                "room_code": "LAB", "building": "Main", "capacity": 25, "room_type": "Lab", "is_active": False,
                "confirm_deactivate": True,
            }).status_code == 200
            draft = start()
            assert client.get(f"/schedules/{draft}/status", headers=coord).json()["status"] == "Draft"
            report = client.get(f"/schedules/{draft}/conflicts?format=csv", headers=coord)
            assert "Add a suitable Lab room" in report.text
            assert client.get(f"/schedules/{first}/entries", headers=coord).json()["entries"] == entries
            table = store["timetable_entries"]
            with store.engine.connect() as connection:
                assert connection.scalar(select(func.count()).select_from(table)) == 3
    finally:
        store.engine.dispose()


def test_UC_08_first_timetable_default_generation_browser(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    seed(url)
    artifacts = LOCAL / "evidence" / "phase3"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts, worker=True) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(address)
        browser_sign_in(page, "coordinator")
        page.get_by_role("link", name="Generate timetable").click()
        expect(page.get_by_label("Academic term")).to_have_value("1")
        page.get_by_role("button", name="Generate", exact=True).click()
        try:
            page.get_by_role("link", name="View timetable").click(timeout=40_000)
        except Exception:
            print(page.locator("main").inner_text())
            raise
        expect(page.get_by_role("heading", name="Weekly timetable")).to_be_visible()
        expect(page.get_by_text("CS101 · Lecture", exact=True)).to_be_visible()
        expect(page.get_by_text("CS102 · Lab continued", exact=True)).to_be_visible()
        expect(page.get_by_text("2 sessions", exact=True)).to_be_visible()
        page.screenshot(path=artifacts / "weekly-timetable.png", full_page=True)
        page.reload()
        expect(page.get_by_text("CS101 · Lecture", exact=True)).to_be_visible()
        page.set_viewport_size({"width": 360, "height": 800})
        page.get_by_label("Room", exact=True).select_option(label="LAB")
        expect(page.get_by_text("1 session", exact=True)).to_be_visible()
        expect(page.get_by_text("CS101 · Lecture", exact=True)).to_have_count(0)
        assert page.evaluate("document.documentElement.scrollWidth") == 360
        context.close()
        browser.close()

