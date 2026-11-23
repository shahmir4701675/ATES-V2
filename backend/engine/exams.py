"""Exam conflict graph, DSATUR starting point and exact session/room model."""

from collections import defaultdict
from itertools import combinations
from math import ceil
from time import monotonic

import networkx as nx
from ortools.sat.python import cp_model


from backend.engine.exam_data import Exam, ExamResult


def conflict_graph(problem):
    graph = nx.Graph()
    graph.add_nodes_from(problem.courses)
    graph.add_edges_from(
        edge for courses in problem.by_student.values() for edge in combinations(courses, 2)
    )
    return graph


def dsatur(problem):
    graph = conflict_graph(problem)
    return nx.coloring.greedy_color(graph, strategy="saturation_largest_first")


def stable_room_search(problem, course, remaining):
    size = len(problem.courses[course]["students"])
    by_building = defaultdict(list)
    for room in remaining:
        by_building[problem.rooms[room]["building"]].append(room)
    groups = [list(remaining), *by_building.values()]
    candidates = []
    for group in groups:
        alloc = {}
        seats = size
        for room in sorted(group, key=lambda key: (-problem.rooms[key]["capacity"], key)):
            alloc[room] = min(seats, problem.rooms[room]["capacity"])
            seats -= alloc[room]
            if seats == 0:
                candidates.append(alloc)
                break
    if not candidates:
        return None
    return min(candidates, key=lambda rooms: (
        len(rooms) * problem.weight("ES02") +
        (len({problem.rooms[room]["building"] for room in rooms}) - 1) * problem.weight("ES03"),
        len(rooms), sorted(rooms),
    ))


def heuristic(problem, colors):
    if problem.pins:
        return None
    groups = defaultdict(list)
    for course, color in colors.items():
        groups[color].append(course)
    left = list(problem.slots)
    by_student_day = defaultdict(int)
    by_batch_day = defaultdict(int)
    assignments = []
    for group in groups.values():
        choices = []
        for key in left:
            date = problem.slots[key]["exam_date"]
            if "E02" in problem.rules and any(
                by_student_day[student, date] >= problem.limit()
                for course in group for student in problem.courses[course]["students"]
            ):
                continue
            cost = sum(by_batch_day[batch, date] for course in group for batch in problem.courses[course]["batches"])
            choices.append((cost, key))
        if not choices:
            return None
        _, key = min(choices)
        date = problem.slots[key]["exam_date"]
        left.remove(key)
        rooms = list(problem.rooms)
        for course in sorted(group, key=lambda key: (-len(problem.courses[key]["students"]), key)):
            alloc = stable_room_search(problem, course, rooms)
            if not alloc:
                return None
            rooms = [room for room in rooms if room not in alloc]
            assignments.append(Exam(course, key, alloc))
            for student in problem.courses[course]["students"]:
                by_student_day[student, date] += 1
            for batch in problem.courses[course]["batches"]:
                by_batch_day[batch, date] += 1
    return tuple(sorted(assignments, key=lambda item: item.course))


def exact(problem, deadline, seed, cancel):
    model = cp_model.CpModel()
    sessions = list(problem.slots)
    positions = {session: index for index, session in enumerate(sessions)}
    dates = list(dict.fromkeys(problem.slots[slot]["exam_date"] for slot in sessions))
    date_indexes = [dates.index(problem.slots[slot]["exam_date"]) for slot in sessions]
    assigned = {}
    by_date = {}
    room_intervals = defaultdict(list)
    room_seats = {}
    objective = []
    for course, info in problem.courses.items():
        if cancel and cancel():
            return "interrupted", ()
        if monotonic() >= deadline:
            return "unknown", ()
        session = model.new_int_var(0, len(sessions) - 1, f"session:{course}")
        assigned[course] = session
        day = model.new_int_var(0, len(dates) - 1, f"day:{course}")
        model.add_element(session, date_indexes, day)
        for index in range(len(dates)):
            present = model.new_bool_var(f"attends:{course}:{index}")
            model.add(day == index).only_enforce_if(present)
            model.add(day != index).only_enforce_if(present.Not())
            by_date[course, index] = present

        pinned = problem.pins.get(course)
        if pinned:
            if pinned["slot"] not in positions:
                return "infeasible", ()
            model.add(session == positions[pinned["slot"]])
        seats = {}
        by_building = defaultdict(list)
        for room, record in problem.rooms.items():
            uses = model.new_bool_var(f"uses:{course}:{room}")
            count = model.new_int_var(0, min(record["capacity"], len(info["students"])), f"seats:{course}:{room}")
            model.add(count > 0).only_enforce_if(uses)
            model.add(count == 0).only_enforce_if(uses.Not())
            room_intervals[room].append(model.new_optional_fixed_size_interval_var(
                session, 1, uses, f"room:{course}:{room}"))
            seats[room] = count
            by_building[record["building"]].append(uses)
            if pinned:
                model.add(count == pinned["rooms"].get(str(room), 0))
            objective.append(problem.weight("ES02") * uses)
        room_seats[course] = seats
        model.add(sum(seats.values()) == len(info["students"]))
        if weight := problem.weight("ES03"):
            for used in by_building.values():
                building = model.new_bool_var(f"building-used:{course}")
                model.add_max_equality(building, used)
                objective.append(weight * building)

    for left, right in conflict_graph(problem).edges:
        model.add(assigned[left] != assigned[right])
    for intervals in room_intervals.values():
        model.add_no_overlap(intervals)
    if "E02" in problem.rules:
        for courses in {tuple(courses) for courses in problem.by_student.values()}:
            if len(courses) > problem.limit():
                for index in range(len(dates)):
                    model.add(sum(by_date[course, index] for course in courses) <= problem.limit())
    if weight := problem.weight("ES01"):
        for courses in problem.by_batch.values():
            for index in range(len(dates)):
                count = model.new_int_var(0, len(courses), "batch exams")
                excess = model.new_int_var(0, len(courses), "same-day batch exams")
                model.add(count == sum(by_date[course, index] for course in courses))
                model.add_max_equality(excess, [0, count - 1])
                objective.append(weight * excess)
    model.minimize(sum(objective))

    remaining = deadline - monotonic()
    if remaining <= 0:
        return "unknown", ()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    if cancel:
        cancel.bind(solver)
    answer = solver.solve(model)
    if cancel and cancel():
        return "interrupted", ()
    if answer == cp_model.MODEL_INVALID:
        raise RuntimeError(solver.solution_info())
    status = solver.status_name(answer).lower()
    if status in {"optimal", "feasible"}:
        return status, tuple(Exam(course, sessions[solver.value(session)], {
            room: solver.value(count) for room, count in room_seats[course].items() if solver.value(count)
        }) for course, session in assigned.items())
    return status, ()


def solve_exams(problem, time_limit, seed, cancel=None):
    started = monotonic()
    colors = dsatur(problem)
    count = max(colors.values(), default=-1) + 1
    if count <= len(problem.slots):
        candidate = heuristic(problem, colors)
        if candidate:
            return ExamResult("feasible", candidate, colors=count)
    status, assignments = exact(problem, started + time_limit, seed, cancel)
    reason = None
    if status == "infeasible":
        minimum = certified_session_count(problem, colors, started + time_limit, seed)
        reason = (
            f"At least {minimum} exam sessions are necessary because of shared students. "
            f"Only {len(problem.slots)} sessions exist. Add at least {minimum - len(problem.slots)}." 
            if minimum > len(problem.slots) else
            "No exam timetable satisfies the student clashes, daily exam limits and available rooms in the defined sessions."
        )
        reason += " Courses: " + ", ".join(row["course_code"] for row in problem.courses.values())
    elif status == "unknown":
        reason = "Time limit reached before finding a feasible exam schedule."
    elif status == "interrupted":
        reason = "Exam scheduling was interrupted."
    return ExamResult(status, assignments, reason, fallback=True, colors=count)


def certified_session_count(problem, colors, deadline, seed):
    graph = conflict_graph(problem)
    lower_bound = len(nx.algorithms.approximation.max_clique(graph))
    upper_bound = max(colors.values(), default=-1) + 1
    remaining = deadline - monotonic()
    if lower_bound == upper_bound or upper_bound <= len(problem.slots) or remaining < .1:
        return lower_bound
    model = cp_model.CpModel()
    selected = {course: model.new_int_var(1, upper_bound, f"color:{course}") for course in graph.nodes}
    count = model.new_int_var(lower_bound, upper_bound, "colors used")
    for left, right in graph.edges:
        model.add(selected[left] != selected[right])
    for course, value in colors.items():
        model.add_hint(selected[course], value + 1)
    model.add_max_equality(count, selected.values())
    model.minimize(count)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.solve(model)
    return max(lower_bound, ceil(solver.best_objective_bound))

