"""Scope and filters shared by schedule views and exports."""

from backend.services import scheduling, versions

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def filtered_view(connection, store, actor, schedule, details, filters):
    payload = scheduling.view_entries(connection, store, schedule["schedule_id"], details)
    payload = versions.scope_view(actor, schedule, payload)
    if schedule["schedule_type"] == "Exam":
        courses = {row["course_id"]: row for row in payload["courses"]}
        slots = {row["exam_slot_id"]: row for row in payload["exam_slots"]}
        entries = [
            row for row in payload["entries"]
            if (not filters.course or row["course"] == filters.course)
            and (not filters.date or slots[row["slot"]]["exam_date"] == filters.date.isoformat())
            and (not filters.batch or str(filters.batch) in courses[row["course"]]["batches"])
            and (not filters.room or str(filters.room) in row["rooms"])
            and (not filters.instructor or str(filters.instructor) in courses[row["course"]]["instructors"])
        ]
        entries.sort(key=lambda row: (slots[row["slot"]]["exam_date"], slots[row["slot"]]["start_time"], row["course"]))
    else:
        slots = {row["slot_id"]: row for row in payload["slots"]}
        offerings = {row["offering_id"]: row for row in payload["offerings"]}
        entries = [
            row for row in payload["entries"]
            if (not filters.course or offerings[row["offering"]]["course_id"] == filters.course)
            and (not filters.day or slots[row["slots"][0]]["day_of_week"] == filters.day)
            and (not filters.room or row["room"] == filters.room)
            and (not filters.batch or row["batch"] == filters.batch)
            and (not filters.instructor or row["instructor"] == filters.instructor)
        ]
    return {**payload, "entries": entries}


def logical_rows(schedule, payload):
    rooms = {row["room_id"]: row["room_code"] for row in payload["rooms"]}
    if schedule["schedule_type"] == "Exam":
        courses = {row["course_id"]: row for row in payload["courses"]}
        slots = {row["exam_slot_id"]: row for row in payload["exam_slots"]}
        for entry in payload["entries"]:
            course = courses[entry["course"]]
            slot = slots[entry["slot"]]
            date = "/".join(reversed(slot["exam_date"].split("-")))
            yield {"day": date, "start": slot["start_time"][:5], "end": slot["end_time"][:5],
                   "course": course["course_code"], "title": course["title"], "type": "Exam",
                   "instructor": ", ".join(course["instructors"].values()),
                   "room": ", ".join(rooms[int(key)] for key in entry["rooms"]),
                   "seats": ", ".join(f"{rooms[int(key)]}: {seats}" for key, seats in entry["rooms"].items()),
                   "batch": ", ".join(course["batches"].values()), "batches": course["batches"],
                   "instructors": course["instructors"]}
    else:
        offerings = {row["offering_id"]: row for row in payload["offerings"]}
        slots = {row["slot_id"]: row for row in payload["slots"]}
        for entry in payload["entries"]:
            offering = offerings[entry["offering"]]
            first, last = slots[entry["slots"][0]], slots[entry["slots"][-1]]
            batch = f"{offering['program_code']} {offering['batch_year']} {offering['section']}"
            yield {"day": WEEKDAYS[first["day_of_week"] - 1], "start": first["start_time"][:5], "end": last["end_time"][:5],
                   "course": offering["course_code"], "title": offering["title"], "type": entry["kind"],
                   "instructor": offering["full_name"], "room": rooms[entry["room"]], "batch": batch,
                   "batches": {str(entry["batch"]): batch}, "instructors": {str(entry["instructor"]): offering["full_name"]}}

