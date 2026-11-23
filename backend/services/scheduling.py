"""Timetable readiness, immutable inputs, versioning and scoped reader data."""

from collections import defaultdict
from dataclasses import asdict
import os
from sqlalchemy import func, select

from backend.api.errors import problem
from backend.engine.timetable_data import Timetable, issue
from backend.services import master
from backend.services.accounts import insert
from backend.services.exam_scheduling import exam_view, freeze_exams, persist_exams
from backend.services.rules import MANDATORY, RULE_DEFAULTS, default_config
from backend.services.security import audit, utc_now


def snapshot(connection, store, term, config_id, source_id, lab_block_slots):
    term_id = term["term_id"]
    slots = []
    issues = []
    for row in master.slot_rows(connection, store, term_id):
        slots.append({
            **dict(row), "start_time": row["start_time"].isoformat(), "end_time": row["end_time"].isoformat(),
            "minutes": master.to_minute(row["end_time"]) - master.to_minute(row["start_time"]),
        })
    durations = {slot["minutes"] for slot in slots}
    if len(durations) != 1 or 0 in durations:
        issues.append(issue("Grid", "Save a weekly grid with equal-length teaching slots."))
    slot_minutes = next(iter(durations)) if len(durations) == 1 and 0 not in durations else None
    entries = store["course_offerings"]
    batches = store["batches"]
    courses = store["courses"]
    instructors = store["instructors"]
    query = select(entries, courses.c.course_code, courses.c.title, courses.c.lecture_hours, courses.c.lab_hours,
                   batches.c.program_code, batches.c.batch_year, batches.c.section, instructors.c.full_name,
                   courses.c.is_active.label("course_active"), batches.c.is_active.label("batch_active"),
                   instructors.c.is_active.label("instructor_active")).join(
        courses, entries.c.course_id == courses.c.course_id,
    ).join(batches, entries.c.batch_id == batches.c.batch_id).join(
        instructors, entries.c.instructor_id == instructors.c.instructor_id,
    ).where(entries.c.term_id == term_id).order_by(entries.c.offering_id)
    offerings = []
    for row in connection.execute(query).mappings():
        if not all(row[key] for key in ("course_active", "batch_active", "instructor_active")):
            issues.append(issue("Offering", "Select an active course, instructor and batch for this offering.", row["course_code"]))
        if slot_minutes:
            try:
                expected = master.demand(row, slot_minutes)
            except ValueError as exc:
                issues.append(issue("H08", str(exc), row["course_code"]))
                continue
            if lab_block_slots and expected["lab_slots"] % lab_block_slots:
                issues.append(issue("H08", f"Lab demand does not divide into {lab_block_slots}-slot blocks. Adjust the block length or contact hours.",
                                     row["course_code"]))
                continue
            offerings.append({**dict(row), **expected})
    if not connection.scalar(select(entries.c.offering_id).where(entries.c.term_id == term_id).limit(1)):
        issues.append(issue("Offerings", "Add at least one course offering for this term."))
    rooms = store["rooms"]
    available = store["instructor_availability"]
    rules = store["constraint_rules"]
    result = {
        "term_name": term["name"], "slots": slots, "offerings": offerings, "lab_block_slots": lab_block_slots,
        "first_weekday": first_weekday(),
        "rooms": [dict(row) for row in connection.execute(select(rooms).where(rooms.c.is_active.is_(True))
                  .order_by(rooms.c.room_id)).mappings()],
        "instructors": [dict(row) for row in connection.execute(select(
            instructors.c.instructor_id, instructors.c.max_daily_hours, instructors.c.max_weekly_hours,
        ).where(instructors.c.instructor_id.in_(sorted({row["instructor_id"] for row in offerings})))
            .order_by(instructors.c.instructor_id)).mappings()],
        "unavailable": [list(row) for row in connection.execute(select(
            available.c.instructor_id, available.c.slot_id,
        ).where(available.c.slot_id.in_([slot["slot_id"] for slot in slots]),
                available.c.is_available.is_(False)).order_by(available.c.instructor_id, available.c.slot_id))],
        "rules": [dict(row) for row in connection.execute(select(
            rules.c.rule_code, rules.c.rule_type, rules.c.is_enabled, rules.c.weight, rules.c.param_value,
        ).where(rules.c.config_id == config_id).order_by(rules.c.rule_code)).mappings()],
        "previous": previous_assignments(connection, store, source_id) if source_id else {},
    }
    expected = {code for code, _, _, _ in RULE_DEFAULTS["Timetable"]}
    actual = {rule["rule_code"] for rule in result["rules"]}
    disabled = {rule["rule_code"] for rule in result["rules"] if not rule["is_enabled"]}
    if expected != actual or disabled.intersection(MANDATORY):
        issues.append(issue("Configuration", "Choose a configuration with all timetable rules and mandatory rules enabled."))
    return result, issues


def first_weekday():
    value = os.getenv("ATES_FIRST_WEEKDAY", "1")
    if value not in {"1", "2", "3", "4", "5", "6", "7"}:
        raise ValueError("ATES_FIRST_WEEKDAY must be a weekday number from 1 to 7.")
    return int(value)


def previous_assignments(connection, store, source_id, *, include_display=False):
    entries = store["timetable_entries"]
    slots = store["time_slots"]
    assignments = {}
    query = select(entries).join(slots, entries.c.slot_id == slots.c.slot_id).where(
        entries.c.schedule_id == source_id,
    ).order_by(slots.c.day_of_week, slots.c.slot_index, entries.c.entry_id)
    for row in connection.execute(query).mappings():
        key = row["session_key"]
        if key is None:
            if row["is_locked"]:
                raise problem(409, "This older schedule has a lock without a logical session identifier.")
            continue
        entry = assignments.setdefault(key, {"room": row["room_id"], "slots": [], "is_locked": row["is_locked"],
                                             "is_manual_override": row["is_manual_override"]})
        entry["slots"].append(row["slot_id"])
        if include_display and "key" not in entry:
            entry.update(key=key, offering=row["offering_id"], instructor=row["instructor_id"],
                         batch=row["batch_id"], kind=row["session_type"])
    return assignments


def readiness(problem):
    # Test each offering independently. Global clashes are decided by the solver.
    issues = []
    capacities = defaultdict(int)
    tasks_checked = set()
    for task in problem.tasks.values():
        offering = problem.offerings[task.offering]
        capacities[task.batch] += task.length
        fingerprint = (task.offering, task.kind)
        if fingerprint in tasks_checked and task.key not in problem.pins:
            continue
        tasks_checked.add(fingerprint)
        pin = problem.pins.get(task.key)
        rooms = [key for key, room in problem.rooms.items()
                 if ("H04" not in problem.rules or room["capacity"] >= task.size)
                 and ("H05" not in problem.rules or room["room_type"] == task.kind)]
        slots = [window for window in problem.starts(task)
                 if all(("H07" not in problem.rules or not problem.slots[key]["is_blocked"])
                        and ("H06" not in problem.rules or (task.instructor, key) not in problem.unavailable)
                        for key in window)]
        if pin and (pin["room"] not in rooms or tuple(pin["slots"]) not in slots):
            issues.append(issue("Locked", "A locked session no longer fits this term’s inputs. Unlock it or restore its room and slot.", task.key))
        elif not rooms:
            issues.append(issue("Rooms", f"Add a suitable {task.kind} room for {task.size} students.", offering["course_code"]))
        elif not slots:
            issues.append(issue("Slots", f"Provide an available window of {task.length} slot(s).", offering["course_code"]))
    for key in problem.pins.keys() - problem.tasks.keys():
        issues.append(issue("Locked", "A locked session is missing from the new requirements.", key))
    available = sum("H07" not in problem.rules or not slot["is_blocked"] for slot in problem.slots.values())
    for batch, count in sorted(capacities.items()):
        if count > available:
            issues.append(issue("Slots", f"This batch needs {count} teaching slots and only {available} are open.", str(batch)))
    return issues


def add_conflicts(connection, store, schedule_id, issues):
    if not issues:
        return
    connection.execute(store["conflict_log"].insert().inline(), [
        {"schedule_id": schedule_id, "conflict_type": item["code"], "severity": "Hard",
         "description": item["message"], "entity_ref": item.get("entity")}
        for item in issues
    ])


def submit(connection, store, actor, form):
    master.serialize_term_change(connection)
    terms = store["academic_terms"]
    term = master.by_id(connection, terms, form.term_id, "term_id", lock=True)
    runs = store["schedule_runs"]
    schedules = store["schedules"]
    duplicate = connection.execute(select(schedules, runs.c.input_snapshot).join(runs, schedules.c.schedule_id == runs.c.schedule_id)
        .where(runs.c.request_token == str(form.request_token))).mappings().first()
    if duplicate:
        if (duplicate["generated_by"] != actor or duplicate["term_id"] != form.term_id
                or duplicate["schedule_type"] != form.schedule_type
                or duplicate["input_snapshot"].get("source_id") != form.source_id
                or (form.config_id and duplicate["config_id"] != form.config_id)):
            raise problem(409, "This request identifier has already been used.")
        return {field: duplicate[field] for field in schedules.c.keys()}
    master.ensure_editable(term)
    source = None
    if form.source_id:
        source = master.by_id(connection, schedules, form.source_id)
        if source["term_id"] != form.term_id or source["schedule_type"] != form.schedule_type or source["status"] in {"Draft", "Generating"}:
            raise problem(422, "Select a completed version of the same term and schedule type.", "source_id")
    configs = store["scheduling_configs"]
    config_id = form.config_id or default_config(connection, store, actor, form.term_id, form.schedule_type)
    config = master.by_id(connection, configs, config_id, "config_id")
    if config["term_id"] != form.term_id or config["schedule_type"] != form.schedule_type:
        raise problem(422, "Select a configuration for this term and schedule type.", "config_id")
    source_id = source["schedule_id"] if source else None
    if form.schedule_type == "Exam":
        frozen, defects = freeze_exams(connection, store, term, config_id, source_id)
    else:
        frozen, defects = snapshot(connection, store, term, config_id, source_id, config["lab_block_slots"])
        defects += readiness(Timetable(frozen))
    frozen["type"] = form.schedule_type
    frozen["source_id"] = form.source_id
    frozen["seed"] = config["random_seed"]
    frozen["time_limit"] = config["solver_time_limit_s"]
    version = connection.scalar(select(func.max(schedules.c.version_no)).where(
        schedules.c.term_id == form.term_id, schedules.c.schedule_type == form.schedule_type,
    )) or 0
    row = insert(connection, schedules, {
        "term_id": form.term_id, "config_id": config_id, "schedule_type": form.schedule_type,
        "version_no": version + 1, "status": "Draft" if defects else "Generating", "generated_by": actor,
    })
    key = row["schedule_id"]
    connection.execute(runs.insert().values(
        schedule_id=key, request_token=str(form.request_token), input_snapshot=frozen,
        outcome="Correct the input before generating." if defects else None,
    ))
    add_conflicts(connection, store, key, defects)
    audit(connection, store, actor, "generation_rejected" if defects else "generation_requested", "schedules", key)
    return row


def get_schedule(connection, store, key, lock=False):
    row = master.by_id(connection, store["schedules"], key, lock=lock)
    runs = store["schedule_runs"]
    details = connection.execute(select(runs).where(runs.c.schedule_id == key)).mappings().first()
    return row, details


def run_summary(row, details):
    result = dict(row)
    if details:
        result.update({
            "revision": details["revision"], "term_name": details["input_snapshot"]["term_name"],
            "outcome": details["outcome"],
            "has_copy": row["status"] == "Draft" and bool(details["baseline"]),
            "statistics": details["statistics"],
            "phase": ("Solving" if details["claim_id"] else "Queued") if row["status"] == "Generating" else row["status"],
            "elapsed": max(0, ((details["finished_at"] or utc_now()) - details["started_at"]).total_seconds())
                if details["started_at"] else 0,
        })
    return result


def stop_run(connection, store, actor, key):
    row, details = get_schedule(connection, store, key, lock=True)
    if row["status"] != "Generating" or not details:
        return run_summary(row, details)
    end_run(connection, store, key, "interrupted", "Cancelled by coordinator.", actor,
            seconds=(utc_now() - (details["started_at"] or row["generated_at"])).total_seconds())
    return run_summary(*get_schedule(connection, store, key))


def end_run(connection, store, key, status, reason, actor, *, seconds, assignments=None, score=None, defects=(),
            statistics=None):
    schedules = store["schedules"]
    runs = store["schedule_runs"]
    entries = store["timetable_entries"]
    accepted = assignments is not None
    payload = None
    if accepted:
        snapshot = connection.scalar(select(runs.c.input_snapshot).where(runs.c.schedule_id == key))
        payload = [asdict(item) for item in assignments]
        if snapshot.get("type") == "Exam":
            persist_exams(connection, store, key, assignments, snapshot)
        else:
            timetable = Timetable(snapshot)
            connection.execute(entries.insert().inline(), [
                {"schedule_id": key, "offering_id": task.offering, "batch_id": task.batch,
                 "instructor_id": task.instructor, "session_type": task.kind, "slot_id": slot,
                 "room_id": entry.room, "session_key": entry.key, "is_locked": entry.key in timetable.pins}
                for entry in assignments for task in (timetable.tasks[entry.key],) for slot in entry.slots
            ])
    connection.execute(schedules.update().where(schedules.c.schedule_id == key).values(
        status="Generated" if accepted else "Infeasible", solver_status=status,
        objective_score=score, run_seconds=min(max(seconds, 0), 999999),
    ))
    connection.execute(runs.update().where(runs.c.schedule_id == key).values(
        baseline=payload, finished_at=utc_now(), heartbeat_at=None, outcome=reason, statistics=statistics,
    ))
    if reason and not accepted:
        add_conflicts(connection, store, key, [issue(status, reason), *defects])
    audit(connection, store, actor, "generation_completed" if accepted else "generation_ended", "schedules", key, status)


def view_entries(connection, store, key, details):
    if not details:
        return {"entries": [], "slots": [], "rooms": [], "offerings": [], "courses": [], "exam_slots": []}
    frozen = details["input_snapshot"]
    if frozen.get("type") == "Exam":
        return exam_view(connection, store, key, details)
    current = previous_assignments(connection, store, key, include_display=True)
    enrolled = {row["offering_id"]: row["enrolled_count"] for row in frozen["offerings"]}
    entries = [{**value, "length": len(value["slots"]), "size": enrolled[value["offering"]]}
               for value in current.values() if value["offering"] in enrolled]
    return {"entries": entries, "slots": frozen["slots"], "rooms": frozen["rooms"], "offerings": frozen["offerings"],
            "first_weekday": frozen.get("first_weekday", 1)}

