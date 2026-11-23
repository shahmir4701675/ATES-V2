"""Check concrete candidates without using CP-SAT variables or expressions."""

from collections import Counter, defaultdict

from backend.engine.timetable_data import issue


def validate(problem, assignments):
    defects = []
    usage = {code: set() for code in ("H01", "H02", "H03")}
    daily = defaultdict(Counter)
    actual = Counter(item.key for item in assignments)
    for key in sorted(set(problem.tasks) | set(actual)):
        if actual[key] != int(key in problem.tasks):
            defects.append(issue("H08", "The schedule must contain each required session exactly once.", key))
    for item in assignments:
        task = problem.tasks.get(item.key)
        room = problem.rooms.get(item.room)
        if not task:
            continue
        if not room:
            defects.append(issue("H04", "The assigned room is missing.", item.key))
        else:
            if "H04" in problem.rules and room["capacity"] < task.size:
                defects.append(issue("H04", "Room capacity is below enrolled count.", item.key))
            if "H05" in problem.rules and room["room_type"] != task.kind:
                defects.append(issue("H05", "Room type does not match the session.", item.key))
        if len(item.slots) != task.length:
            defects.append(issue("H08", "Assigned duration does not match the required duration.", item.key))
        if not problem.consecutive(item.slots):
            defects.append(issue("H09", "The occupied slots must be consecutive on one day.", item.key))
        if (pin := problem.pins.get(item.key)) and (pin["room"] != item.room or tuple(pin["slots"]) != item.slots):
            defects.append(issue("Locked", "The session moved from its locked slot or room.", item.key))
        for slot_id in item.slots:
            slot = problem.slots.get(slot_id)
            if not slot:
                defects.append(issue("H08", "The assigned slot is missing.", item.key))
                continue
            for code, resource, description in (
                ("H01", task.instructor, "The instructor is already teaching."),
                ("H02", item.room, "The room is already occupied."),
                ("H03", task.batch, "The batch already has a session."),
            ):
                if (resource, slot_id) in usage[code]:
                    defects.append(issue(code, description, item.key))
                usage[code].add((resource, slot_id))
            if "H06" in problem.rules and (task.instructor, slot_id) in problem.unavailable:
                defects.append(issue("H06", "The instructor is unavailable.", item.key))
            if "H07" in problem.rules and slot["is_blocked"]:
                defects.append(issue("H07", "The slot is blocked.", item.key))
            daily[task.instructor][slot["day_of_week"]] += slot["minutes"]
    if "H10" in problem.rules:
        for teacher, days in daily.items():
            instructor = problem.instructors[teacher]
            if any(minutes > instructor["max_daily_hours"] * 60 for minutes in days.values()):
                defects.append(issue("H10", "Daily teaching hours exceeded.", str(teacher)))
            if sum(days.values()) > instructor["max_weekly_hours"] * 60:
                defects.append(issue("H10", "Weekly teaching hours exceeded.", str(teacher)))
    return defects


def objective(problem, assignments):
    batch_slots = defaultdict(set)
    instructor_slots = defaultdict(set)
    offering_days = Counter()
    batch_days = Counter()
    counts = Counter()
    for item in assignments:
        task = problem.tasks[item.key]
        day = problem.slots[item.slots[0]]["day_of_week"]
        offering_days[task.offering, day] += 1
        batch_days[task.batch, day] += 1
        batch_slots[task.batch, day].update(item.slots)
        instructor_slots[task.instructor, day].update(item.slots)
        previous = problem.previous.get(item.key)
        if previous and (previous["room"] != item.room or tuple(previous["slots"]) != item.slots):
            counts["S05"] += 1
        counts["S06"] += problem.fit_cost(task, item.room)
    for (_, day), used in batch_slots.items():
        positions = [index for index, key in enumerate(problem.windows[day]) if key in used]
        counts["S01"] += positions[-1] - positions[0] + 1 - len(positions)
    counts["S02"] = sum(count - 1 for count in offering_days.values())
    if "S03" in problem.rules:
        limit = problem.parameter("S03", 5)
        counts["S03"] = sum(max(0, count - limit) for count in batch_days.values())
    if "S04" in problem.rules:
        limit = problem.parameter("S04", 3)
        for (_, day), used in instructor_slots.items():
            run = 0
            previous = None
            for key in problem.windows[day]:
                if key in used:
                    run = run + 1 if previous and problem.consecutive((previous, key)) else 1
                    counts["S04"] += int(run > limit)
                    previous = key
                else:
                    run = 0
                    previous = None
    return -sum(problem.weight(code) * count for code, count in counts.items())

