"""Deterministic feasible starting candidates for the CP-SAT search."""

from collections import Counter, defaultdict
from time import monotonic

from backend.engine.timetable_data import Assignment
from backend.engine.validator import validate


def initial_candidate(problem, eligible, deadline, cancel):
    instructor_slots, batch_slots, room_slots = defaultdict(set), defaultdict(set), defaultdict(set)
    daily, weekly, same_offering, same_batch = Counter(), Counter(), Counter(), Counter()
    assignments = {}
    tasks = sorted(problem.tasks.values(), key=lambda task: (
        task.key not in problem.pins,
        len(eligible[task.key][0]) * len(eligible[task.key][1]),
        -task.length,
        task.key,
    ))
    for task in tasks:
        if (cancel and cancel()) or monotonic() >= deadline:
            return ()
        starts, rooms = eligible[task.key]
        prior = problem.previous.get(task.key, {})
        suitable_rooms = sorted(rooms, key=lambda key: (
            problem.weight("S06") * problem.fit_cost(task, key), key,
        ))
        chosen = None
        for window in starts:
            first = problem.slots[window[0]]
            day = first["day_of_week"]
            duration = sum(problem.slots[key]["minutes"] for key in window)
            if (instructor_slots[task.instructor].intersection(window) or batch_slots[task.batch].intersection(window)
                    or ("H10" in problem.rules and (
                        daily[task.instructor, day] + duration > problem.instructors[task.instructor]["max_daily_hours"] * 60
                        or weekly[task.instructor] + duration > problem.instructors[task.instructor]["max_weekly_hours"] * 60
                    ))):
                continue
            room = next((key for key in suitable_rooms if not room_slots[key].intersection(window)), None)
            if room is None:
                continue
            if tuple(prior.get("slots", [])) == window and prior.get("room") in suitable_rooms \
                    and not room_slots[prior["room"]].intersection(window):
                prior_room = prior["room"]
                if (problem.fit_cost(task, prior_room) - problem.fit_cost(task, room)) * problem.weight("S06") <= problem.weight("S05"):
                    room = prior_room
            penalty = (
                problem.weight("S02") * min(1, same_offering[task.offering, day])
                + problem.weight("S06") * problem.fit_cost(task, room)
                + int(bool(prior) and (room != prior["room"] or window != tuple(prior["slots"]))) * problem.weight("S05")
            )
            if "S03" in problem.rules:
                penalty += problem.weight("S03") * int(same_batch[task.batch, day] >= problem.parameter("S03", 5))
            existing = batch_slots[task.batch].intersection(problem.windows[day])
            if existing and problem.weight("S01"):
                indexes = [problem.slots[key]["slot_index"] for key in existing.union(window)]
                penalty += problem.weight("S01") * (max(indexes) - min(indexes) + 1 - len(indexes))
            rank = penalty, first["day_of_week"], first["slot_index"], room
            if not chosen or rank < chosen[0]:
                chosen = rank, room, window, day, duration
        if not chosen:
            return ()
        _, room, window, day, duration = chosen
        assignments[task.key] = Assignment(task.key, room, window)
        instructor_slots[task.instructor].update(window)
        batch_slots[task.batch].update(window)
        room_slots[room].update(window)
        daily[task.instructor, day] += duration
        weekly[task.instructor] += duration
        same_batch[task.batch, day] += 1
        same_offering[task.offering, day] += 1
    candidate = tuple(assignments[key] for key in problem.tasks)
    return candidate if not validate(problem, candidate) else ()

