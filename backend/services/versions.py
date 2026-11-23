"""Guarded edits, duplication, approval and scoped schedule reads."""

from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import func, select

from backend.api.errors import problem
from backend.engine.exam_validator import exam_objective, validate_exams
from backend.engine.exam_data import Exam, ExamProblem
from backend.engine.timetable_data import Assignment, Timetable
from backend.engine.validator import objective, validate
from backend.services import master, scheduling
from backend.services.accounts import insert
from backend.services.exam_scheduling import current_exams, persist_exams
from backend.services.security import audit, utc_now

STAFF = {"Coordinator", "Approver"}


def readable(user, schedule):
    if user["role"] not in STAFF and schedule["status"] != "Published":
        raise problem(404, "This schedule is unavailable.")


def scope_view(user, schedule, payload):
    if user["role"] in STAFF or user["role"] == "Administrator":
        return payload
    if schedule["schedule_type"] == "Timetable":
        field, key = ("batch", user["batch_id"]) if user["role"] == "Student" else ("instructor", user["instructor_id"])
        entries = [row for row in payload["entries"] if row[field] == key]
        offered = {row["offering"] for row in entries}
        rooms = {row["room"] for row in entries}
        return {**payload, "entries": entries, "rooms": [row for row in payload["rooms"] if row["room_id"] in rooms],
                "offerings": [row for row in payload["offerings"] if row["offering_id"] in offered]}
    field, key = ("batches", str(user["batch_id"])) if user["role"] == "Student" else ("instructors", str(user["instructor_id"]))
    matching = [{**row, field: {key: row[field][key]}} for row in payload["courses"] if key in row[field]]
    if user["role"] == "Student":
        matching = [{**row, "instructors": {}} for row in matching]
    elif user["role"] == "Faculty":
        matching = [{**row, "batches": {}} for row in matching]
    courses = {row["course_id"] for row in matching}
    exams = [row for row in payload["entries"] if row["course"] in courses]
    rooms = {int(room) for row in exams for room in row["rooms"]}
    return {**payload, "courses": matching, "entries": exams,
            "rooms": [row for row in payload["rooms"] if row["room_id"] in rooms]}


def guard(connection, store, key, revision, states):
    schedule, run = scheduling.get_schedule(connection, store, key, lock=True)
    if schedule["status"] not in states or not run:
        raise problem(409, "This version cannot be changed in its current state.")
    if run["revision"] != revision:
        raise problem(409, "This version changed. Reload it and try again.")
    term = master.by_id(connection, store["academic_terms"], schedule["term_id"])
    master.ensure_editable(term)
    return schedule, run


def load(connection, store, schedule, run):
    key = schedule["schedule_id"]
    exam = schedule["schedule_type"] == "Exam"
    snapshot = run["input_snapshot"]
    if exam:
        raw = current_exams(connection, store, key)
        problem_data = ExamProblem({**snapshot, "previous": {}})
        items = [Exam(row["course"], row["slot"], {int(room): seats for room, seats in row["rooms"].items()})
                 for row in raw.values()]
    else:
        raw = scheduling.previous_assignments(connection, store, key)
        problem_data = Timetable({**snapshot, "previous": {
            key: {**prior, "is_locked": False} for key, prior in snapshot.get("previous", {}).items()
        }})
        items = [Assignment(ref, row["room"], tuple(row["slots"])) for ref, row in raw.items()]
    return exam, raw, problem_data, items


def defects_for(exam, problem_data, entries):
    return (validate_exams if exam else validate)(problem_data, entries)


def ensure_valid(exam, data, entries, status=409):
    defects = defects_for(exam, data, entries)
    if defects:
        first = defects[0]
        raise problem(status, f"{first['code']}. {first['message']}", issues=defects)


def index_key(exam, item):
    return str(item.course) if exam else item.key


def save_assignment(connection, store, schedule_id, exam, problem_data, item, original, overridden):
    if exam:
        exams = store["exam_entries"]
        allocations = store["exam_room_allocations"]
        exam_id = connection.scalar(select(exams.c.exam_entry_id).where(
            exams.c.schedule_id == schedule_id, exams.c.course_id == item.course,
        ))
        connection.execute(allocations.delete().where(allocations.c.exam_entry_id == exam_id))
        connection.execute(exams.update().where(exams.c.exam_entry_id == exam_id).values(
            exam_slot_id=item.slot, is_manual_override=overridden,
        ))
        connection.execute(allocations.insert(), [
            {"exam_entry_id": exam_id, "room_id": room, "seats_allocated": seats} for room, seats in item.rooms.items()
        ])
    else:
        entries = store["timetable_entries"]
        connection.execute(entries.delete().where(entries.c.schedule_id == schedule_id, entries.c.session_key == item.key))
        task = problem_data.tasks[item.key]
        connection.execute(entries.insert(), [
            {"schedule_id": schedule_id, "session_key": item.key, "offering_id": task.offering,
             "instructor_id": task.instructor, "batch_id": task.batch, "room_id": item.room, "slot_id": slot,
             "session_type": task.kind, "is_locked": original["is_locked"], "is_manual_override": overridden}
            for slot in item.slots
        ])


def normalize_baseline(exam, raw):
    if exam:
        return [Exam(row["course"], row["slot"], {int(room): seats for room, seats in row["rooms"].items()}) for row in raw]
    return [Assignment(row["key"], row["room"], tuple(row["slots"])) for row in raw]


def bump(connection, store, key, run, values=None):
    versions = store["schedule_runs"]
    revision = run["revision"] + 1
    connection.execute(versions.update().where(versions.c.schedule_id == key).values(revision=revision, **(values or {})))
    return revision


def move(connection, store, actor, key, form):
    schedule, run = guard(connection, store, key, form.revision, {"Generated"})
    exam, raw, data, entries = load(connection, store, schedule, run)
    original = raw.get(form.entry)
    if not original:
        raise problem(404, "This entry is missing from the version.")
    if original["is_locked"]:
        raise problem(409, "Unlock this entry before moving it.")
    if exam:
        candidate = Exam(original["course"], form.slot_id, form.seats or {int(room): seats for room, seats in original["rooms"].items()})
    else:
        task = data.tasks[form.entry]
        slots = next((slots for slots in data.starts(task) if slots[0] == form.slot_id), None)
        if slots is None:
            raise problem(409, "H09. Choose a starting slot with enough consecutive teaching time.")
        candidate = Assignment(form.entry, form.room_id or original["room"], slots)
    changed = [candidate if index_key(exam, item) == form.entry else item for item in entries]
    ensure_valid(exam, data, changed)
    baseline = {index_key(exam, item): item for item in normalize_baseline(exam, run["baseline"] or [])}
    save_assignment(connection, store, key, exam, data, candidate, original, baseline.get(form.entry) != candidate)
    store_score(connection, store, key, exam, data, changed)
    audit(connection, store, actor, "entry_moved", "Schedule", key, form.entry)
    return {"revision": bump(connection, store, key, run)}


def store_score(connection, store, key, exam, data, entries):
    table = store["schedules"]
    connection.execute(table.update().where(table.c.schedule_id == key).values(
        objective_score=(exam_objective if exam else objective)(data, entries),
    ))


def lock_entry(connection, store, actor, key, form):
    schedule, run = guard(connection, store, key, form.revision, {"Generated"})
    if schedule["schedule_type"] == "Exam":
        table = store["exam_entries"]
        identity = table.c.course_id
        try:
            target = int(form.entry)
        except ValueError:
            raise problem(422, "Choose a valid exam identifier.") from None
    else:
        table = store["timetable_entries"]
        identity = table.c.session_key
        target = form.entry
    if not connection.execute(table.update().where(table.c.schedule_id == key, identity == target)
                              .values(is_locked=form.locked)).rowcount:
        raise problem(404, "This entry is missing from the version.")
    audit(connection, store, actor, "entry_locked" if form.locked else "entry_unlocked", "Schedule", key, form.entry)
    return {"revision": bump(connection, store, key, run)}


def undo(connection, store, actor, key, revision):
    schedule, run = guard(connection, store, key, revision, {"Generated"})
    exam, raw, data, entries = load(connection, store, schedule, run)
    original = normalize_baseline(exam, run["baseline"] or [])
    ensure_valid(exam, data, original)
    altered = {index_key(exam, item) for item in entries} & {ref for ref, value in raw.items() if value["is_manual_override"]}
    if not altered:
        return {"revision": run["revision"]}
    if exam:
        table = store["exam_room_allocations"]
        rows = store["exam_entries"]
        ids = select(rows.c.exam_entry_id).where(rows.c.schedule_id == key, rows.c.course_id.in_([int(ref) for ref in altered]))
        connection.execute(table.delete().where(table.c.exam_entry_id.in_(ids)))
    else:
        table = store["timetable_entries"]
        connection.execute(table.delete().where(table.c.schedule_id == key, table.c.session_key.in_(altered)))
    for item in original:
        ref = index_key(exam, item)
        if ref in altered:
            save_assignment(connection, store, key, exam, data, item, raw[ref], False)
    store_score(connection, store, key, exam, data, original)
    audit(connection, store, actor, "schedule_undo", "Schedule", key)
    return {"revision": bump(connection, store, key, run)}


def published_query(store, term_id, kind):
    table = store["schedules"]
    return select(table).where(table.c.term_id == term_id, table.c.schedule_type == kind, table.c.status == "Published")


def publish(connection, store, actor, key, form):
    master.serialize_term_change(connection)
    schedule, run = guard(connection, store, key, form.revision, {"Generated"})
    current = connection.execute(published_query(store, schedule["term_id"], schedule["schedule_type"])
                                 .with_for_update()).mappings().first()
    if (current["schedule_id"] if current else None) != form.replace_id:
        raise problem(409, "The current published version changed. Reload the review summary.")
    if not form.confirmed:
        raise problem(422, "Confirm publication and replacement before continuing.")
    exam, _, data, items = load(connection, store, schedule, run)
    ensure_valid(exam, data, items, status=422)
    table = store["schedules"]
    if current:
        connection.execute(table.update().where(table.c.schedule_id == current["schedule_id"]).values(status="Archived"))
        audit(connection, store, actor, "schedule_archived", "Schedule", current["schedule_id"])
    connection.execute(table.update().where(table.c.schedule_id == key).values(
        status="Published", approved_by=actor, published_at=utc_now(),
    ))
    bump(connection, store, key, run)
    audit(connection, store, actor, "schedule_published", "Schedule", key)
    return scheduling.run_summary(*scheduling.get_schedule(connection, store, key))


def review(connection, store, key):
    schedule, run = scheduling.get_schedule(connection, store, key)
    if schedule["status"] != "Generated" or not run:
        raise problem(409, "Only a Generated version can be reviewed for publication.")
    exam, _, data, entries = load(connection, store, schedule, run)
    current = connection.execute(published_query(store, schedule["term_id"], schedule["schedule_type"])).mappings().first()
    issues = defects_for(exam, data, entries)
    return {"revision": run["revision"], "entries": len(entries), "issues": issues,
            "score": schedule["objective_score"], "published_id": current["schedule_id"] if current else None,
            "published_version": current["version_no"] if current else None}


def duplicate(connection, store, actor, key, revision):
    master.serialize_term_change(connection)
    source, run = guard(connection, store, key, revision, {"Generated", "Published", "Archived", "Draft", "Infeasible"})
    schedules = store["schedules"]
    next_version = connection.scalar(select(func.max(schedules.c.version_no)).where(
        schedules.c.term_id == source["term_id"], schedules.c.schedule_type == source["schedule_type"],
    )) + 1
    copy = insert(connection, schedules, {
        "term_id": source["term_id"], "config_id": source["config_id"], "schedule_type": source["schedule_type"],
        "version_no": next_version, "status": "Draft", "generated_by": actor,
    })
    new_id = copy["schedule_id"]
    exam, _, data, entries = load(connection, store, source, run)
    snapshot = run["input_snapshot"]
    baseline = [asdict(entry) for entry in entries] or None
    connection.execute(store["schedule_runs"].insert().values(
        schedule_id=new_id, request_token=str(uuid4()), input_snapshot=snapshot, baseline=baseline,
        outcome="Validate this copy before publishing." if baseline else "Correct the inputs and generate a new version.",
        statistics=run["statistics"],
    ))
    if entries and exam:
        persist_exams(connection, store, new_id, entries, snapshot)
    elif entries:
        table = store["timetable_entries"]
        fields = [column for column in table.c if column.name not in {"entry_id", "schedule_id"}]
        rows = connection.execute(select(*fields).where(table.c.schedule_id == key)).mappings().all()
        connection.execute(table.insert(), [{**row, "schedule_id": new_id} for row in rows])
    audit(connection, store, actor, "schedule_duplicated", "Schedule", new_id, f"Copied {key}")
    return {"schedule_id": new_id}


def verify_copy(connection, store, actor, key, revision):
    schedule, run = guard(connection, store, key, revision, {"Draft"})
    if not run["baseline"]:
        raise problem(409, "This Draft has no copied entries to validate.")
    exam, _, data, entries = load(connection, store, schedule, run)
    ensure_valid(exam, data, entries, status=422)
    schedules = store["schedules"]
    connection.execute(schedules.update().where(schedules.c.schedule_id == key).values(status="Generating"))
    connection.execute(schedules.update().where(schedules.c.schedule_id == key).values(
        status="Generated", solver_status="feasible", run_seconds=0,
    ))
    store_score(connection, store, key, exam, data, entries)
    bump(connection, store, key, run, {"outcome": None})
    audit(connection, store, actor, "schedule_copy_validated", "Schedule", key)
    return scheduling.run_summary(*scheduling.get_schedule(connection, store, key))

