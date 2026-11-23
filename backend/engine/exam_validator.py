"""Verify allocations by counting actual students, exams, rooms and seats."""

from collections import Counter, defaultdict

from backend.engine.timetable_data import issue


def validate_exams(problem, assignments):
    issues = []
    used_courses = Counter(item.course for item in assignments)
    in_session = defaultdict(set)
    on_date = Counter()
    rooms = set()
    for course in used_courses.keys() | problem.courses.keys():
        if used_courses[course] != int(course in problem.courses):
            issues.append(issue("E05", "Each examinable course requires exactly one exam.", str(course)))
    for item in assignments:
        course = problem.courses.get(item.course)
        slot = problem.slots.get(item.slot)
        if not course or not slot:
            issues.append(issue("E05", "The course or exam session is missing.", str(item.course)))
            continue
        key = course["course_code"]
        if in_session[item.slot].intersection(course["students"]):
            issues.append(issue("E01", "Students have simultaneous exams.", key))
        in_session[item.slot].update(course["students"])
        for student in course["students"]:
            on_date[student, slot["exam_date"]] += 1
        if "E02" in problem.rules and any(on_date[student, slot["exam_date"]] > problem.limit() for student in course["students"]):
            issues.append(issue("E02", "Students exceed the daily exam limit.", key))
        if sum(item.rooms.values()) != len(course["students"]):
            issues.append(issue("E03", "Total seats must match the candidate count.", key))
        for room, seats in item.rooms.items():
            if room not in problem.rooms or not 0 < seats <= problem.rooms[room]["capacity"]:
                issues.append(issue("E03", "Seat allocation exceeds room capacity or uses an unknown room.", key))
            if (item.slot, room) in rooms:
                issues.append(issue("E04", "A room is allocated twice in the same session.", key))
            rooms.add((item.slot, room))
        pin = problem.pins.get(item.course)
        if pin and (item.slot != pin["slot"] or item.rooms != {int(room): count for room, count in pin["rooms"].items()}):
            issues.append(issue("Locked", "The exam moved from its locked session or rooms.", key))
    return issues


def exam_objective(problem, assignments):
    dates = Counter()
    rooms = buildings = 0
    for item in assignments:
        course = problem.courses[item.course]
        date = problem.slots[item.slot]["exam_date"]
        for batch in course["batches"]:
            dates[batch, date] += 1
        rooms += len(item.rooms)
        buildings += len({problem.rooms[room]["building"] for room in item.rooms}) - 1
    return -(problem.weight("ES01") * sum(value - 1 for value in dates.values()) +
             problem.weight("ES02") * rooms + problem.weight("ES03") * buildings)

