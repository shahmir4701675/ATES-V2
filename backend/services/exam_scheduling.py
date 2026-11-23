"""Freeze distinct exam candidates, date windows and room metadata for the worker."""

from collections import defaultdict

from sqlalchemy import select

from backend.api.errors import problem
from backend.engine.timetable_data import issue
from backend.services import master
from backend.services.accounts import insert
from backend.services.rules import MANDATORY, RULE_DEFAULTS
from backend.services.security import audit


def exam_offerings(connection, store, term):
    courses = store["courses"]
    offerings = store["course_offerings"]
    batches = store["batches"]
    excluded = store["term_exam_exclusions"]
    instructors = store["instructors"]
    return connection.execute(select(
        offerings, courses.c.course_code, courses.c.title, batches.c.strength, batches.c.program_code,
        batches.c.batch_year, batches.c.section, instructors.c.full_name,
    ).join(courses, offerings.c.course_id == courses.c.course_id)
     .join(batches, offerings.c.batch_id == batches.c.batch_id)
     .join(instructors, offerings.c.instructor_id == instructors.c.instructor_id)
     .where(offerings.c.term_id == term, offerings.c.course_id.not_in(
         select(excluded.c.course_id).where(excluded.c.term_id == term),
     )).order_by(courses.c.course_code, offerings.c.offering_id)).mappings().all()


def current_exams(connection, store, schedule_id):
    exams = store["exam_entries"]
    rooms = store["exam_room_allocations"]
    allocations = defaultdict(dict)
    ids = select(exams.c.exam_entry_id).where(exams.c.schedule_id == schedule_id)
    for row in connection.execute(select(rooms).where(rooms.c.exam_entry_id.in_(ids))
                                  .order_by(rooms.c.room_id)).mappings():
        allocations[row["exam_entry_id"]][str(row["room_id"])] = row["seats_allocated"]
    return {
        str(row["course_id"]): {"course": row["course_id"], "slot": row["exam_slot_id"],
                                "student_count": row["student_count"], "is_locked": row["is_locked"],
                                "is_manual_override": row["is_manual_override"],
                                "rooms": allocations[row["exam_entry_id"]]}
        for row in connection.execute(select(exams).where(exams.c.schedule_id == schedule_id)
                                      .order_by(exams.c.course_id)).mappings()
    }


def freeze_exams(connection, store, term, config_id, source):
    term_id = term["term_id"]
    defects = []
    slots = store["exam_slots"]
    rooms = store["rooms"]
    rules = store["constraint_rules"]
    enrollments = store["enrollments"]
    users = store["users"]
    selected = exam_offerings(connection, store, term_id)
    explicit = defaultdict(list)
    batch_users = defaultdict(list)
    for offering, student, role in connection.execute(select(
        enrollments.c.offering_id, enrollments.c.student_id, users.c.role,
    ).join(users, enrollments.c.student_id == users.c.user_id).where(
        enrollments.c.offering_id.in_([row["offering_id"] for row in selected]),
    ).order_by(enrollments.c.student_id)):
        if role != "Student":
            defects.append(issue("Roster", "An enrollment must reference a Student account.", str(offering)))
        explicit[offering].append(f"user:{student}")

    batch_ids = sorted({row["batch_id"] for row in selected})
    for user_id, batch_id in connection.execute(select(users.c.user_id, users.c.batch_id).where(
        users.c.role == "Student", users.c.batch_id.in_(batch_ids),
    ).order_by(users.c.user_id)):
        batch_users[batch_id].append(f"user:{user_id}")
    courses = {}
    for row in selected:
        course = courses.setdefault(row["course_id"], {"course_id": row["course_id"], "course_code": row["course_code"],
                                                       "title": row["title"], "students": set(), "batches": {},
                                                       "instructors": {}, "fallback": False})
        batch_id = row["batch_id"]
        course["batches"][str(batch_id)] = f"{row['program_code']} {row['batch_year']} {row['section']}"
        course["instructors"][str(row["instructor_id"])] = row["full_name"]
        roster = explicit[row["offering_id"]]
        if roster:
            if len(roster) != row["enrolled_count"]:
                defects.append(issue("Roster", f"Expected {row['enrolled_count']} enrolled students, found {len(roster)}.",
                                     row["course_code"]))
            course["students"].update(roster)
        else:
            known = batch_users[batch_id]
            if len(known) > row["strength"] or row["enrolled_count"] > row["strength"]:
                defects.append(issue("Roster", "Reconcile batch strength and student counts before using the batch roster.",
                                     row["course_code"]))
            course["fallback"] = True
            course["students"].update(known)
            course["students"].update(f"batch:{batch_id}:{i}" for i in range(max(0, row["strength"] - len(known))))
    for course in courses.values():
        course["students"] = sorted(course["students"])
    room_rows = [dict(row) for row in connection.execute(select(rooms).where(rooms.c.is_active.is_(True))
                                                         .order_by(rooms.c.room_id)).mappings()]
    slot_rows = [{**row, **{key: row[key].isoformat() for key in ("exam_date", "start_time", "end_time")}}
                 for row in connection.execute(select(slots).where(slots.c.term_id == term_id)
                                               .order_by(slots.c.exam_date, slots.c.start_time)).mappings()]
    rule_rows = [dict(row) for row in connection.execute(select(rules).where(rules.c.config_id == config_id)
                                                         .order_by(rules.c.rule_code)).mappings()]
    previous = current_exams(connection, store, source) if source else {}
    if not courses:
        defects.append(issue("Courses", "Add an examinable course offering for this term."))
    if not slot_rows:
        defects.append(issue("Sessions", "Add at least one dated exam session in Settings."))
    available_seats = sum(room["capacity"] for room in room_rows)
    for course in courses.values():
        count = len(course["students"])
        if count > available_seats or not 0 < count <= 32767:
            defects.append(issue("Rooms", f"{count} candidates require suitable rooms. Active rooms provide {available_seats} seats.",
                                 course["course_code"]))
    for key, exam in previous.items():
        if exam["is_locked"] and (int(key) not in courses or exam["slot"] not in {row["exam_slot_id"] for row in slot_rows}
                                  or set(map(int, exam["rooms"])) - {row["room_id"] for row in room_rows}):
            defects.append(issue("Locked", "Restore the date, course or rooms of a locked exam, or unlock it first.", key))
    if ({row["rule_code"] for row in rule_rows} != {rule[0] for rule in RULE_DEFAULTS["Exam"]}
            or any(row["rule_code"] in MANDATORY and not row["is_enabled"] for row in rule_rows)):
        defects.append(issue("Configuration", "Choose a configuration with all exam rules and mandatory rules enabled."))
    return {"term_name": term["name"], "courses": list(courses.values()), "exam_slots": slot_rows,
            "rooms": room_rows, "previous": previous, "rules": rule_rows}, defects


def persist_exams(connection, store, key, assignments, snapshot):
    exams = store["exam_entries"]
    seats = store["exam_room_allocations"]
    courses = {row["course_id"]: row for row in snapshot["courses"]}
    for exam in assignments:
        row = insert(connection, exams, {"schedule_id": key, "course_id": exam.course, "exam_slot_id": exam.slot,
                    "student_count": len(courses[exam.course]["students"]),
                    "is_locked": bool(snapshot["previous"].get(str(exam.course), {}).get("is_locked"))})
        connection.execute(seats.insert().inline(), [{"exam_entry_id": row["exam_entry_id"], "room_id": room,
                                              "seats_allocated": count} for room, count in exam.rooms.items()])


def exam_view(connection, store, key, details):
    frozen = details["input_snapshot"]
    courses = [{key: value for key, value in row.items() if key != "students"} for row in frozen["courses"]]
    return {"entries": list(current_exams(connection, store, key).values()),
            "exam_slots": frozen["exam_slots"], "rooms": frozen["rooms"], "courses": courses}


def set_examinable(connection, store, actor, term_id, course_id, included):
    master.serialize_term_change(connection)
    master.ensure_editable(master.by_id(connection, store["academic_terms"], term_id, lock=True))
    master.by_id(connection, store["courses"], course_id)
    offerings = store["course_offerings"]
    if not connection.scalar(select(offerings.c.offering_id).where(
        offerings.c.course_id == course_id, offerings.c.term_id == term_id,
    ).limit(1)):
        raise problem(422, "This course has no offerings in the term.")
    table = store["term_exam_exclusions"]
    key = (table.c.term_id == term_id, table.c.course_id == course_id)
    if included:
        connection.execute(table.delete().where(*key))
    elif not connection.scalar(select(table.c.course_id).where(*key)):
        connection.execute(table.insert().values(term_id=term_id, course_id=course_id))
    audit(connection, store, actor, "exam_inclusion_changed", "Course", course_id, f"Term {term_id}: {included}")

