"""Deterministic A-1 and doubled engine fixtures with verified witness schedules."""

import json
from collections import defaultdict
from time import perf_counter

from backend.engine.exam_data import ExamProblem
from backend.engine.exam_validator import validate_exams
from backend.engine.exams import solve_exams
from backend.engine.timetable import solve
from backend.engine.timetable_data import Assignment, Timetable
from backend.engine.validator import objective, validate
from backend.services.rules import RULE_DEFAULTS


def rules(schedule_type):
    return [{"rule_code": code, "rule_type": kind, "weight": weight, "param_value": value, "is_enabled": True}
            for code, kind, weight, value in RULE_DEFAULTS[schedule_type]]


def teaching(scale):
    slots = [{
        "slot_id": day * 8 + slot + 1, "day_of_week": day + 1, "slot_index": slot + 1,
        "start_time": f"{8 + slot:02}:00:00", "end_time": f"{9 + slot:02}:00:00",
        "minutes": 60, "is_blocked": slot == 3,
    } for day in range(6) for slot in range(8)]
    rooms = [
        {"room_id": room + 1, "capacity": 75 + room % 5, "building": f"Building {room // 8 + 1}",
         "room_type": "Lab" if room % 4 == 0 else "Lecture"} for room in range(60 * scale)
    ]
    offerings = [{
        "offering_id": index + 1, "course_id": ((index // 40) * 11 + index % 40) % 80 + 1,
        "batch_id": index % 40 + 1, "instructor_id": index % 80 + 1, "enrolled_count": 75,
        "lecture_slots": 1, "lab_slots": 2 if index % 5 == 0 else 0,
    } for index in range(150 * scale)]
    assert len({(row["course_id"], row["batch_id"]) for row in offerings}) == len(offerings)
    return {"slots": slots, "rooms": rooms, "offerings": offerings,
            "instructors": [{"instructor_id": key + 1, "max_daily_hours": 4, "max_weekly_hours": 18} for key in range(80)],
            "unavailable": [], "rules": rules("Timetable")}


def witness(problem):
    instructor_slots, room_slots, batch_slots = defaultdict(set), defaultdict(set), defaultdict(set)
    minutes = defaultdict(int)
    assignments = []
    for task in problem.tasks.values():
        placed = None
        for window in problem.starts(task):
            day = problem.slots[window[0]]["day_of_week"]
            if any(problem.slots[key]["is_blocked"] for key in window):
                continue
            if minutes[task.instructor, day] + task.length > 4:
                continue
            if instructor_slots[task.instructor].intersection(window) or batch_slots[task.batch].intersection(window):
                continue
            for room_id, room in problem.rooms.items():
                if room["room_type"] != task.kind or room_slots[room_id].intersection(window):
                    continue
                placed = Assignment(task.key, room_id, window)
                break
            if placed:
                break
        assert placed is not None, task
        assignments.append(placed)
        room_slots[placed.room].update(placed.slots)
        instructor_slots[task.instructor].update(placed.slots)
        batch_slots[task.batch].update(placed.slots)
        minutes[task.instructor, day] += task.length
    assert validate(problem, assignments) == []
    return assignments


def exam_reference():
    data = teaching(1)
    data["exam_slots"] = [{"exam_slot_id": slot + 1, "exam_date": f"2027-04-{slot // 2 + 1:02}"}
                          for slot in range(18)]
    data["courses"] = [
        {"course_id": course + 1, "course_code": f"CS{course + 100}",
         "batches": {str(course % 40 + 1): f"Batch {course % 40 + 1}"},
         "students": [str((course % 40) * 75 + candidate) for candidate in range(75)]}
        for course in range(80)
    ]
    # Five shared-elective candidates each appear on a different batch's second course.
    for index in range(5):
        data["courses"][index + 41]["students"].append(str(index * 75))
    assert len({student for course in data["courses"] for student in course["students"]}) == 3000
    data["rules"] = rules("Exam")
    return data


def benchmark(scale, seconds):
    snapshot = teaching(scale)
    problem = Timetable(snapshot)
    expected = witness(problem)
    started = perf_counter()
    result = solve(problem, seconds, 1)
    elapsed = perf_counter() - started
    accepted = bool(result.assignments)
    return {"kind": "Timetable", "scale": scale, "offerings": len(snapshot["offerings"]),
            "rooms": len(snapshot["rooms"]), "slots": len(snapshot["slots"]), "seed": 1, "time_limit": seconds,
            "elapsed": round(elapsed, 3), "status": result.status, "witness_sessions": len(expected),
            "saved_sessions": len(result.assignments), "hard_conflicts": len(validate(problem, result.assignments)) if accepted else None,
            "score": objective(problem, result.assignments) if accepted else None}


def benchmark_exams():
    problem = ExamProblem(exam_reference())
    started = perf_counter()
    result = solve_exams(problem, 30, 1)
    elapsed = perf_counter() - started
    return {"kind": "Exam", "courses": len(problem.courses), "candidates": len(problem.by_student),
            "rooms": len(problem.rooms), "seed": 1, "time_limit": 30, "elapsed": round(elapsed, 3),
            "status": result.status, "saved_exams": len(result.assignments),
            "hard_conflicts": len(validate_exams(problem, result.assignments)) if result.assignments else None,
            "fallback": result.fallback}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    for measurement in (benchmark_exams, lambda: benchmark(1, args.seconds), lambda: benchmark(2, args.seconds)):
        print(json.dumps(measurement()), flush=True)

