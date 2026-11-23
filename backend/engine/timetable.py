"""Deterministic CP-SAT model, constructed independently of result validation."""

from collections import defaultdict
from time import monotonic

from ortools.sat.python import cp_model

from backend.engine.initial_timetable import initial_candidate
from backend.engine.timetable_data import Assignment, Result
from backend.engine.validator import objective

MODEL_RULES = {
    "H04": lambda problem, task, room: room["capacity"] >= task.size,
    "H05": lambda problem, task, room: room["room_type"] == task.kind,
}
SLOT_RULES = {
    "H06": lambda problem, task, slot: (task.instructor, slot["slot_id"]) not in problem.unavailable,
    "H07": lambda problem, task, slot: not slot["is_blocked"],
}


def eligible_rooms(problem, task):
    return [key for key, room in problem.rooms.items()
            if all(test(problem, task, room) for code, test in MODEL_RULES.items() if code in problem.rules)]


def eligible_starts(problem, task):
    return [slots for slots in problem.starts(task)
            if all(test(problem, task, problem.slots[key]) for key in slots
                   for code, test in SLOT_RULES.items() if code in problem.rules)]


def choices_for(problem, task):
    starts = eligible_starts(problem, task)
    rooms = eligible_rooms(problem, task)
    pin = problem.pins.get(task.key)
    if pin:
        starts = [slots for slots in starts if slots == tuple(pin["slots"])]
        rooms = [key for key in rooms if key == pin["room"]]
    return starts, rooms


class Model:
    def __init__(self, problem):
        self.problem = problem
        self.model = cp_model.CpModel()
        self.positions = {slot_id: index for index, slot_id in enumerate(problem.slots)}
        self.tasks = {}
        self.instructor_intervals = defaultdict(list)
        self.batch_intervals = defaultdict(list)
        self.room_intervals = defaultdict(list)
        self.teacher_slot = defaultdict(list)
        self.batch_slot = defaultdict(list)
        self.offer_day = defaultdict(list)
        self.batch_day = defaultdict(list)
        self.teacher_day_minutes = defaultdict(list)
        self.penalties = []

    def add_task(self, task, starts, rooms, initial):
        model = self.model
        start = model.new_int_var_from_domain(
            cp_model.Domain.from_values([self.positions[slots[0]] for slots in starts]), f"start:{task.key}")
        interval = model.new_fixed_size_interval_var(start, task.length, f"session:{task.key}")
        self.instructor_intervals[task.instructor].append(interval)
        self.batch_intervals[task.batch].append(interval)
        positions = {}
        room_choices = {}
        for slots in starts:
            slot_start = slots[0]
            choice = model.new_bool_var(f"slot:{task.key}:{slot_start}")
            model.add(start == self.positions[slot_start]).only_enforce_if(choice)
            positions[slots] = choice
            day = self.problem.slots[slot_start]["day_of_week"]
            self.offer_day[task.offering, day].append(choice)
            self.batch_day[task.batch, day].append(choice)
            minutes = sum(self.problem.slots[key]["minutes"] for key in slots)
            self.teacher_day_minutes[task.instructor, day].append(minutes * choice)
            for key in slots:
                self.teacher_slot[task.instructor, key].append(choice)
                self.batch_slot[task.batch, key].append(choice)
        model.add_exactly_one(positions.values())
        for room_id in rooms:
            choice = model.new_bool_var(f"room:{task.key}:{room_id}")
            self.room_intervals[room_id].append(model.new_optional_fixed_size_interval_var(
                start, task.length, choice, f"room-use:{task.key}:{room_id}"))
            room_choices[room_id] = choice
            if weight := self.problem.weight("S06"):
                self.penalties.append(weight * self.problem.fit_cost(task, room_id) * choice)
        model.add_exactly_one(room_choices.values())
        prior = self.problem.previous.get(task.key)
        if prior and (weight := self.problem.weight("S05")):
            previous_room = room_choices.get(prior["room"])
            previous_start = positions.get(tuple(prior["slots"]))
            if previous_room is not None and previous_start is not None:
                same = model.new_bool_var(f"same:{task.key}")
                model.add_min_equality(same, [previous_room, previous_start])
                self.penalties.append(weight * (1 - same))
            else:
                self.penalties.append(weight)
        self.tasks[task.key] = positions, room_choices
        if initial:
            model.add_hint(start, self.positions[initial.slots[0]])
            for slots, choice in positions.items():
                model.add_hint(choice, int(slots == initial.slots))
            for room_id, choice in room_choices.items():
                model.add_hint(choice, int(room_id == initial.room))

    def add_limits(self):
        for mapping in (self.instructor_intervals, self.room_intervals, self.batch_intervals):
            for intervals in mapping.values():
                self.model.add_no_overlap(intervals)
        if "H10" in self.problem.rules:
            weekly = defaultdict(list)
            for (instructor, _), terms in self.teacher_day_minutes.items():
                limit = self.problem.instructors[instructor]["max_daily_hours"] * 60
                self.model.add(sum(terms) <= limit)
                weekly[instructor].extend(terms)
            for instructor, terms in weekly.items():
                self.model.add(sum(terms) <= self.problem.instructors[instructor]["max_weekly_hours"] * 60)

    def excess(self, groups, threshold, weight):
        if not weight:
            return
        for choices in groups.values():
            if len(choices) > threshold:
                total = self.model.new_int_var(0, len(choices), "session count")
                excess = self.model.new_int_var(0, len(choices), "session excess")
                self.model.add(total == sum(choices))
                self.model.add_max_equality(excess, [0, total - threshold])
                self.penalties.append(weight * excess)

    def occupancy(self, mapping, resource, key):
        choices = mapping[resource, key]
        if not choices:
            return 0
        occupied = self.model.new_bool_var("slot occupied")
        self.model.add(occupied == sum(choices))
        return occupied

    def add_gaps(self):
        if not (weight := self.problem.weight("S01")):
            return
        for batch in self.batch_intervals:
            for windows in self.problem.windows.values():
                count = len(windows)
                busy = [self.occupancy(self.batch_slot, batch, key) for key in windows]
                first = self.model.new_int_var(0, count, "first occupied slot")
                last = self.model.new_int_var(-1, count - 1, "last occupied slot")
                raw_gap = self.model.new_int_var(-count, count, "raw batch gap")
                gap = self.model.new_int_var(0, count, "batch gap")
                self.model.add_min_equality(first, [i + (count - i) * (1 - value) for i, value in enumerate(busy)])
                self.model.add_max_equality(last, [-1 + (i + 1) * value for i, value in enumerate(busy)])
                self.model.add(raw_gap == last - first + 1 - sum(busy))
                self.model.add_max_equality(gap, [0, raw_gap])
                self.penalties.append(weight * gap)

    def add_consecutive(self):
        if not (weight := self.problem.weight("S04")):
            return
        limit = self.problem.parameter("S04", 3)
        for instructor in self.instructor_intervals:
            occupied = {key: self.occupancy(self.teacher_slot, instructor, key) for key in self.problem.slots}
            for windows in self.problem.windows.values():
                for offset in range(len(windows) - limit):
                    slots = windows[offset:offset + limit + 1]
                    if not self.problem.consecutive(slots):
                        continue
                    over = self.model.new_bool_var("consecutive work excess")
                    self.model.add_min_equality(over, [occupied[key] for key in slots])
                    self.penalties.append(weight * over)

    def preferences(self):
        self.excess(self.offer_day, 1, self.problem.weight("S02"))
        if self.problem.weight("S03"):
            self.excess(self.batch_day, self.problem.parameter("S03", 5), self.problem.weight("S03"))
        self.add_gaps()
        self.add_consecutive()
        self.model.minimize(sum(self.penalties))


def solve(problem, time_limit, seed, cancel=None):
    deadline = monotonic() + time_limit
    eligible = {}
    for task in problem.tasks.values():
        if cancel and cancel():
            return Result("interrupted", reason="Cancelled by coordinator.")
        eligible[task.key] = choices_for(problem, task)
        if not all(eligible[task.key]):
            return Result("infeasible", reason=f"No eligible slot/room combination for {task.key}.")
        if monotonic() >= deadline:
            return Result("unknown", reason="Time limit reached during input preparation.")
    incumbent = initial_candidate(problem, eligible, deadline, cancel)
    hinted = {assignment.key: assignment for assignment in incumbent}

    def at_limit():
        if incumbent:
            return Result("feasible", incumbent, "Time limit reached. Saved the best valid timetable found.")
        return Result("unknown", reason="Time limit reached before finding a feasible timetable.")

    model = Model(problem)
    for task in problem.tasks.values():
        if cancel and cancel():
            return Result("interrupted", reason="Cancelled by coordinator.")
        model.add_task(task, *eligible[task.key], hinted.get(task.key))
        if monotonic() >= deadline:
            return at_limit()
    model.add_limits()
    model.preferences()
    # Reserve time for native solver teardown and decoding or validating the last candidate.
    completion_margin = min(2.5, max(0.1, time_limit * 0.05))
    remaining = deadline - monotonic() - completion_margin
    if remaining <= 0:
        return at_limit()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    if cancel:
        cancel.bind(solver)
    status = solver.solve(model.model)
    if cancel and cancel():
        return Result("interrupted", reason="Cancelled by coordinator.")
    if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        candidate = tuple(
            Assignment(key, next(room for room, choice in rooms.items() if solver.boolean_value(choice)),
                       next(slots for slots, choice in starts.items() if solver.boolean_value(choice)))
            for key, (starts, rooms) in model.tasks.items()
        )
        if incumbent and objective(problem, incumbent) > objective(problem, candidate):
            return Result("feasible", incumbent)
        return Result(solver.status_name(status).lower(), candidate)
    if status == cp_model.INFEASIBLE:
        return Result("infeasible", reason="No schedule satisfies all enabled hard rules. Check instructor and batch clashes, teaching-hour limits, and available rooms and slots.")
    if status == cp_model.MODEL_INVALID:
        raise RuntimeError(solver.solution_info())
    return at_limit()

