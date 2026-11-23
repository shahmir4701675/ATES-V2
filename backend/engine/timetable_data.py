"""Snapshot-based timetable problem shared by the solver and validator."""

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    key: str
    offering: int
    instructor: int
    batch: int
    size: int
    kind: str
    length: int


@dataclass(frozen=True)
class Assignment:
    key: str
    room: int
    slots: tuple[int, ...]


@dataclass(frozen=True)
class Result:
    status: str
    assignments: tuple[Assignment, ...] = ()
    reason: str | None = None


def issue(code, message, entity=None):
    return {"code": code, "message": message, "entity": entity}


class Timetable:
    def __init__(self, snapshot):
        self.slots = {row["slot_id"]: row for row in snapshot["slots"]}
        self.rooms = {row["room_id"]: row for row in snapshot["rooms"]}
        self.offerings = {row["offering_id"]: row for row in snapshot["offerings"]}
        self.instructors = {row["instructor_id"]: row for row in snapshot["instructors"]}
        self.rules = {rule["rule_code"]: rule for rule in snapshot["rules"] if rule["is_enabled"]}
        self.unavailable = {tuple(item) for item in snapshot["unavailable"]}
        self.previous = snapshot.get("previous", {})
        self.pins = {key: value for key, value in self.previous.items() if value.get("is_locked")}
        self.windows = defaultdict(list)
        for slot in self.slots.values():
            self.windows[slot["day_of_week"]].append(slot["slot_id"])
        self.tasks = {}
        for offering in self.offerings.values():
            lab_slots = offering["lab_slots"]
            block_size = snapshot.get("lab_block_slots") or lab_slots or 1
            for kind, count, length in (("Lecture", offering["lecture_slots"], 1),
                                        ("Lab", lab_slots // block_size, block_size)):
                for number in range(1, count + 1):
                    key = f"{offering['offering_id']}:{kind}:{number}"
                    self.tasks[key] = Task(key, offering["offering_id"], offering["instructor_id"],
                                           offering["batch_id"], offering["enrolled_count"], kind, length)

    def consecutive(self, slot_ids):
        if not slot_ids or any(slot_id not in self.slots for slot_id in slot_ids):
            return False
        rows = [self.slots[slot_id] for slot_id in slot_ids]
        return all(
            later["day_of_week"] == earlier["day_of_week"]
            and later["slot_index"] == earlier["slot_index"] + 1
            and later["start_time"] == earlier["end_time"]
            for earlier, later in zip(rows, rows[1:])
        )

    def starts(self, task):
        for windows in self.windows.values():
            for offset in range(len(windows) - task.length + 1):
                slots = tuple(windows[offset:offset + task.length])
                if self.consecutive(slots):
                    yield slots

    def parameter(self, code, default):
        return self.rules[code]["param_value"] or default

    def weight(self, code):
        return self.rules.get(code, {}).get("weight", 0)

    def fit_cost(self, task, room_id):
        room = self.rooms[room_id]
        suitable_sizes = sorted({row["capacity"] for row in self.rooms.values() if row["capacity"] >= task.size})
        return suitable_sizes.index(room["capacity"]) if room["capacity"] >= task.size else len(suitable_sizes) + 1

