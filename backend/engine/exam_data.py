"""Exam snapshots and assignments shared by the solver and validator."""

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Exam:
    course: int
    slot: int
    rooms: dict[int, int]


@dataclass(frozen=True)
class ExamResult:
    status: str
    assignments: tuple[Exam, ...] = ()
    reason: str | None = None
    fallback: bool = False
    colors: int = 0


class ExamProblem:
    def __init__(self, snapshot):
        self.courses = {row["course_id"]: row for row in snapshot["courses"]}
        self.slots = {row["exam_slot_id"]: row for row in snapshot["exam_slots"]}
        self.rooms = {row["room_id"]: row for row in snapshot["rooms"]}
        self.rules = {rule["rule_code"]: rule for rule in snapshot["rules"] if rule["is_enabled"]}
        self.pins = {int(key): value for key, value in snapshot.get("previous", {}).items() if value.get("is_locked")}
        self.by_student = defaultdict(list)
        self.by_batch = defaultdict(list)
        for course, row in self.courses.items():
            for student in row["students"]:
                self.by_student[student].append(course)
            for batch in row["batches"]:
                self.by_batch[batch].append(course)

    def weight(self, code):
        return self.rules.get(code, {}).get("weight", 0)

    def limit(self):
        return self.rules.get("E02", {}).get("param_value", 2) or 2

