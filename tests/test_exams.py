"""Exam graph fallback, independent validation and real allocation views."""

import os
import sys

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
import pytest

from backend.api.app import create_app
from backend.cli import LOCAL
from backend.engine.exam_data import Exam, ExamProblem
from backend.engine.exam_validator import exam_objective, validate_exams
from backend.engine.exams import conflict_graph, solve_exams
from backend.services.rules import RULE_DEFAULTS
from conftest import TEST_SECRET
from test_browser import browser_sign_in, running_server
from test_master import login
from test_timetable import seed


def graph_fixture(days=(1, 2, 3)):
    vertices = "ABCDEFG"
    edges = ("AC", "AD", "AE", "BD", "BF", "BG", "CD", "CF", "DG", "EF", "EG")
    return {
        "courses": [{"course_id": key, "course_code": letter, "batches": {"1": "Batch"},
                     "students": [edge for edge in edges if letter in edge]}
                    for key, letter in enumerate(vertices, 1)],
        "exam_slots": [{"exam_slot_id": key, "exam_date": f"2027-04-{day:02}"}
                       for key, day in enumerate(days, 1)],
        "rooms": [{"room_id": room, "capacity": 2, "building": "Main" if room % 2 else "Annex"} for room in range(1, 9)],
        "rules": [{"rule_code": key, "rule_type": kind, "weight": weight, "param_value": value, "is_enabled": True}
                  for key, kind, weight, value in RULE_DEFAULTS["Exam"]],
    }


def test_FR_7_2_exact_fallback_after_four_dsatur_colors():
    problem = ExamProblem(graph_fixture())
    result = solve_exams(problem, 10, 1)
    assert result.fallback and result.colors == 4
    assert len(conflict_graph(problem).edges) == 11
    assert result.status in {"optimal", "feasible"} and len(result.assignments) == 7
    assert any(len(exam.rooms) == 2 for exam in result.assignments)
    assert validate_exams(problem, result.assignments) == []


def test_FR_7_5_infeasible_exam_graph_has_no_assignments():
    problem = ExamProblem(graph_fixture((1, 2)))
    result = solve_exams(problem, 10, 1)
    assert result.status == "infeasible" and not result.assignments
    assert "Add at least 1" in result.reason


@pytest.mark.parametrize("rule", ["E01", "E02", "E03", "E04", "E05"])
def test_E01_E05_reject_bad_candidates(rule):
    frozen = graph_fixture((1, 1, 1))
    frozen["courses"] = [{"course_id": key, "course_code": str(key), "students": ["shared"],
                          "batches": {"1": "Batch"}} for key in range(1, 4)]
    entries = [Exam(1, 1, {1: 1}), Exam(2, 2, {2: 1}), Exam(3, 3, {3: 1})]
    if rule == "E01":
        entries[1] = Exam(2, 1, {2: 1})
    elif rule == "E03":
        entries[0] = Exam(1, 1, {1: 3})
    elif rule == "E04":
        entries[1] = Exam(2, 1, {1: 1})
    elif rule == "E05":
        entries.pop()
    assert rule in {item["code"] for item in validate_exams(ExamProblem(frozen), entries)}


@pytest.mark.parametrize("rule", ["ES01", "ES02", "ES03"])
def test_ES01_ES03_prefer_spread_fewer_rooms_and_one_building(rule):
    frozen = graph_fixture()
    for config in frozen["rules"]:
        if config["rule_type"] == "Soft":
            config["is_enabled"] = config["rule_code"] == rule
    problem = ExamProblem(frozen)
    sample = Exam(1, 1, {1: 1, 3: 2})
    if rule == "ES01":
        assert exam_objective(problem, [sample, Exam(2, 2, {2: 3})]) > exam_objective(
            problem, [sample, Exam(2, 1, {2: 3})])
    elif rule == "ES02":
        assert exam_objective(problem, [sample]) > exam_objective(problem, [Exam(1, 1, {1: 1, 2: 1, 3: 1})])
    else:
        assert exam_objective(problem, [sample]) > exam_objective(problem, [Exam(1, 1, {1: 1, 2: 2})])


def test_UC_09_FR_7_4_split_exam_browser(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    term_id, _ = seed(url)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        coord = login(client, "coordinator")
        for key, name, room_type in [(1, "R101", "Lecture"), (2, "LAB", "Lab")]:
            assert client.put(f"/rooms/{key}", headers=coord, json={
                "room_code": name, "building": "Main", "capacity": 15, "room_type": room_type,
            }).status_code == 200
        for day in (1, 2):
            assert client.post(f"/terms/{term_id}/exam-slots", headers=coord, json={
                "exam_date": f"2027-04-0{day}", "start_time": "09:00", "end_time": "11:00",
            }).status_code == 201
    artifacts = LOCAL / "evidence" / "phase5"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts, worker=True) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(address)
        browser_sign_in(page, "coordinator")
        page.get_by_role("link", name="Exams", exact=True).click()
        page.get_by_role("link", name="Generate exam schedule").click()
        page.get_by_role("button", name="Generate", exact=True).click()
        page.get_by_role("link", name="View exam schedule").click(timeout=40_000)
        expect(page.get_by_text("2 exams", exact=True)).to_be_visible()
        expect(page.get_by_text("R101 · 15 seats", exact=True)).to_have_count(2)
        expect(page.get_by_text("LAB · 10 seats", exact=True)).to_have_count(2)
        page.reload()
        page.set_viewport_size({"width": 360, "height": 800})
        page.get_by_label("Course", exact=True).select_option(label="CS102")
        expect(page.get_by_text("1 exam", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") == 360
        page.screenshot(path=artifacts / "exams-mobile.png", full_page=True)
        context.close()
        browser.close()

def test_FR_7_1_distinct_rosters_across_repeated_and_elective_offerings(migrated_db):
    from backend.data.store import Store
    from backend.services.exam_scheduling import freeze_exams
    from backend.services.master import by_id
    from sqlalchemy import select
    from test_master import new_user

    url = migrated_db.url.render_as_string(hide_password=False)
    term, _ = seed(url)
    with TestClient(create_app(url, TEST_SECRET)) as client:
        coord, admin = login(client, "coordinator"), login(client, "admin")
        response = client.post("/batches", headers=coord, json={
            "department_id": 1, "program_code": "CS", "batch_year": 2026, "section": "B", "strength": 2,
        })
        assert response.status_code == 201, response.text
        batch = response.json()["batch_id"]
        students = [new_user(client, admin, f"student{index}", "Student", batch_id=batch)["user_id"] for index in range(2)]
        for offer, course, instructor in ((1, 1, 1), (2, 2, 2)):
            response = client.put(f"/offerings/{offer}", headers=coord, json={
                "term_id": term, "course_id": course, "batch_id": 1, "instructor_id": instructor, "enrolled_count": 1,
            })
            assert response.status_code == 200, response.text
        response = client.post("/offerings", headers=coord, json={
            "term_id": term, "course_id": 1, "batch_id": batch, "instructor_id": 1, "enrolled_count": 2,
        })
        assert response.status_code == 201, response.text
        repeat = response.json()["offering_id"]
        for offer, student in ((1, students[0]), (2, students[0]), (repeat, students[0]), (repeat, students[1])):
            assert client.post("/enrollments", headers=coord, json={
                "offering_id": offer, "student_id": student,
            }).status_code == 201
        for day in (1, 2):
            assert client.post(f"/terms/{term}/exam-slots", headers=coord, json={
                "exam_date": f"2027-04-0{day}", "start_time": "09:00", "end_time": "11:00",
            }).status_code == 201
    store = Store(url)
    try:
        with store.engine.connect() as connection:
            configs = store["scheduling_configs"]
            config = connection.scalar(select(configs.c.config_id).where(configs.c.schedule_type == "Exam"))
            record = by_id(connection, store["academic_terms"], term)
            frozen, issues = freeze_exams(connection, store, record, config, None)
        assert not issues
        problem = ExamProblem(frozen)
        assert len(problem.courses[1]["students"]) == 2
        assert list(conflict_graph(problem).edges) == [(1, 2)]
        result = solve_exams(problem, 10, 1)
        assert validate_exams(problem, result.assignments) == []
        assert result.assignments[0].slot != result.assignments[1].slot
    finally:
        store.engine.dispose()


