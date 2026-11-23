"""Master data, term activation, stable slot reconciliation and availability."""

from dataclasses import dataclass
from datetime import time

from sqlalchemy import func, or_, select

from backend.api.errors import problem
from backend.services.accounts import insert
from backend.services.rules import default_config
from backend.services.security import audit


@dataclass(frozen=True)
class Resource:
    table: str
    search: tuple
    unique: tuple
    references: tuple = ()


RESOURCES = {
    "departments": Resource("departments", ("code", "name"), ("code",)),
    "terms": Resource("academic_terms", ("name", "status"), ("name",)),
    "courses": Resource("courses", ("course_code", "title"), ("course_code",), (("department_id", "departments"),)),
    "instructors": Resource("instructors", ("full_name", "email"), ("email",), (("department_id", "departments"),)),
    "rooms": Resource("rooms", ("room_code", "building", "room_type"), ("room_code",)),
    "batches": Resource("batches", ("program_code", "section"), ("program_code", "batch_year", "section"),
                        (("department_id", "departments"),)),
    "offerings": Resource("course_offerings", (), ("term_id", "course_id", "batch_id"),
                          (("course_id", "courses"), ("batch_id", "batches"), ("instructor_id", "instructors"))),
    "enrollments": Resource("enrollments", (), ("offering_id", "student_id"),
                            (("offering_id", "course_offerings"), ("student_id", "users"))),
}


def by_id(connection, table, key, field=None, lock=False):
    if not 0 < key <= 2_147_483_647:
        raise problem(422, "Select a valid identifier.", field)
    query = select(table).where(next(iter(table.primary_key)) == key)
    row = connection.execute(query.with_for_update() if lock else query).mappings().first()
    if not row:
        raise problem(422 if field else 404, "This record could not be found.", field)
    return row


def ensure_editable(term):
    if term["status"] == "Closed":
        raise problem(409, "This academic term is closed.")


def list_records(connection, store, name, term_id, search, sort, desc, page):
    resource = RESOURCES[name]
    table = store[resource.table]
    primary = next(iter(table.primary_key))
    query = select(table)
    if term_id and name == "enrollments":
        offerings = store["course_offerings"]
        query = query.join(offerings, table.c.offering_id == offerings.c.offering_id).where(offerings.c.term_id == term_id)
    elif term_id and "term_id" in table.c and name != "terms":
        query = query.where(table.c.term_id == term_id)
    if search and resource.search:
        query = query.where(or_(*(table.c[field].icontains(search, autoescape=True) for field in resource.search)))
    if sort is not None and sort not in table.c:
        raise problem(422, "Choose a supported sort field.", "sort")
    column = table.c[sort or (resource.search[0] if resource.search else primary.name)]
    total = connection.scalar(select(func.count()).select_from(query.subquery()))
    rows = connection.execute(query.order_by(column.desc() if desc else column.asc(), primary).limit(25).offset((page - 1) * 25))
    return {"items": rows.mappings().all(), "total": total, "page": page}


def serialize_term_change(connection):
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(418202612)")


def save_term(connection, store, actor, values, key, form):
    serialize_term_change(connection)
    terms = store["academic_terms"]
    original = by_id(connection, terms, key, lock=True) if key is not None else None
    active = connection.execute(select(terms).where(terms.c.status == "Active").with_for_update()).mappings().first()
    if original and original["status"] == "Closed":
        raise problem(409, "Closed terms are read-only.")
    if values["status"] == "Closed":
        if not original or not form.confirm_close:
            raise problem(422, "Confirm closing the term and archiving its publications.", "status")
        schedules = store["schedules"]
        if connection.scalar(select(schedules.c.schedule_id).where(
            schedules.c.term_id == key, schedules.c.status == "Generating",
        ).limit(1)):
            raise problem(409, "Finish or cancel the running generation before closing the term.", "status")
        if original["status"] == "Active":
            successor = form.successor_id
            candidates = select(terms.c.term_id).where(terms.c.term_id != key, terms.c.status == "Planned")
            if connection.scalar(candidates.limit(1)):
                next_term = connection.scalar(candidates.where(terms.c.term_id == successor)) if successor else None
                if not next_term:
                    raise problem(422, "Select the next active term before closing this one.", "successor_id")
                connection.execute(terms.update().where(terms.c.term_id == key).values(status="Planned"))
                connection.execute(terms.update().where(terms.c.term_id == successor).values(status="Active"))
    elif original and original["status"] == "Active" and values["status"] != "Active":
        raise problem(409, "Activate the next term before changing the current term’s status.", "status")
    if values["status"] == "Active" and active and active["term_id"] != key:
        connection.execute(terms.update().where(terms.c.term_id == active["term_id"]).values(status="Planned"))
    result = save_row(connection, terms, RESOURCES["terms"], values, key)
    if result["status"] != "Closed":
        for kind in ("Timetable", "Exam"):
            default_config(connection, store, actor, result["term_id"], kind)
    if result["status"] == "Closed":
        schedules = store["schedules"]
        archived = connection.execute(schedules.update().where(
            schedules.c.term_id == result["term_id"], schedules.c.status == "Published",
        ).values(status="Archived").returning(schedules.c.schedule_id)).scalars()
        for schedule_id in archived:
            audit(connection, store, actor, "schedule_archived", "Schedule", schedule_id, "Term closed")
        audit(connection, store, actor, "term_closed", "Term", key)
    return result


def save_row(connection, table, resource, values, key):
    primary = next(iter(table.primary_key))
    duplicate = select(primary).where(*(table.c[field] == values[field] for field in resource.unique))
    if key is not None:
        duplicate = duplicate.where(primary != key)
    if connection.scalar(duplicate):
        field = resource.unique[-1]
        label = field.replace("_", " ").removesuffix(" id")
        message = f"This {label} already exists." if len(resource.unique) == 1 else "This combination already exists."
        raise problem(409, message, field)
    if key is None:
        return insert(connection, table, values)
    return connection.execute(table.update().where(primary == key).values(**values).returning(*table.c)).mappings().one()


def save_record(connection, store, actor, name, form, key=None):
    serialize_term_change(connection)
    resource = RESOURCES[name]
    table = store[resource.table]
    values = form.model_dump(exclude={"department", "successor_id", "confirm_close", "confirm_deactivate"})
    if name == "terms":
        row = save_term(connection, store, actor, values, key, form)
    else:
        prior = by_id(connection, table, key, lock=True) if key is not None else None
        if prior and prior.get("is_active") and not values.get("is_active") and not form.confirm_deactivate:
            raise problem(422, "Confirm deactivation. Future offerings and runs may require a replacement.", "is_active")
        if name == "offerings":
            terms = store["academic_terms"]
            for term_id in sorted({values["term_id"], prior["term_id"] if prior else values["term_id"]}):
                ensure_editable(by_id(connection, terms, term_id, "term_id", lock=True))
            if prior and any(prior[field] != values[field] for field in ("course_id", "batch_id", "instructor_id", "term_id")):
                entries = store["timetable_entries"]
                if connection.scalar(select(entries.c.entry_id).where(entries.c.offering_id == key).limit(1)):
                    raise problem(409, "This offering is used by a schedule. Keep its course, batch, instructor and term.")
        for field, target in resource.references:
            record = by_id(connection, store[target], values[field], field)
            if "is_active" in record and not record["is_active"] and (not prior or prior[field] != values[field]):
                raise problem(422, "Select an active record.", field)
            if field == "student_id" and record["role"] != "Student":
                raise problem(422, "Select an account with the Student role.", field)
            if field == "offering_id":
                ensure_editable(by_id(connection, store["academic_terms"], record["term_id"], lock=True))
        row = save_row(connection, table, resource, values, key)
    audit(connection, store, actor, "master_updated" if key else "master_created", name,
          row[next(iter(table.primary_key)).name])
    return row


def remove_enrollment(connection, store, actor, key):
    table = store["enrollments"]
    row = by_id(connection, table, key, lock=True)
    offering = by_id(connection, store["course_offerings"], row["offering_id"])
    ensure_editable(by_id(connection, store["academic_terms"], offering["term_id"], lock=True))
    connection.execute(table.delete().where(table.c.enrollment_id == key))
    audit(connection, store, actor, "enrollment_removed", "enrollments", key)


def slot_rows(connection, store, term_id):
    slots = store["time_slots"]
    return connection.execute(select(slots).where(slots.c.term_id == term_id).order_by(
        slots.c.day_of_week, slots.c.slot_index,
    )).mappings().all()


def to_minute(value):
    return value.hour * 60 + value.minute


def to_time(value):
    return time(*divmod(value, 60))


def save_grid(connection, store, actor, term_id, grid):
    ensure_editable(by_id(connection, store["academic_terms"], term_id, "term_id", lock=True))
    slots = store["time_slots"]
    entries = store["timetable_entries"]
    start = to_minute(grid.first_start)
    wanted = {
        (day, index + 1): (to_time(start + index * grid.slot_minutes), to_time(start + (index + 1) * grid.slot_minutes))
        for day in grid.days for index in range(grid.slots_per_day)
    }
    existing = {(row["day_of_week"], row["slot_index"]): row for row in slot_rows(connection, store, term_id)}
    changed = {key for key, row in existing.items() if wanted.get(key) != (row["start_time"], row["end_time"])}
    if changed and connection.scalar(select(entries.c.entry_id).where(
        entries.c.slot_id.in_([existing[key]["slot_id"] for key in changed])
    ).limit(1)):
        raise problem(409, "A changed slot belongs to a saved version. Use a new term for a different grid.")
    removed = existing.keys() - wanted.keys()
    if removed:
        windows = store["instructor_availability"]
        removed_slots = [existing[key]["slot_id"] for key in removed]
        if any(existing[key]["is_blocked"] for key in removed) or connection.scalar(
            select(windows.c.availability_id).where(windows.c.slot_id.in_(removed_slots)).limit(1)
        ):
            raise problem(409, "Unblock removed slots and clear their availability before shortening the grid.")
        connection.execute(slots.delete().where(slots.c.slot_id.in_(removed_slots)))
    for (day, index), (first, last) in wanted.items():
        key = day, index
        if key in changed:
            connection.execute(slots.update().where(slots.c.slot_id == existing[key]["slot_id"]).values(
                start_time=first, end_time=last,
            ))
        elif key not in existing:
            connection.execute(slots.insert().values(term_id=term_id, day_of_week=day, slot_index=index,
                                                     start_time=first, end_time=last))
    if changed or wanted.keys() - existing.keys():
        audit(connection, store, actor, "grid_saved", "terms", term_id)
    return slot_rows(connection, store, term_id)


def set_block(connection, store, actor, slot_id, form):
    slots = store["time_slots"]
    slot = by_id(connection, slots, slot_id)
    ensure_editable(by_id(connection, store["academic_terms"], slot["term_id"], lock=True))
    connection.execute(slots.update().where(slots.c.slot_id == slot_id).values(
        is_blocked=form.is_blocked, block_reason=form.block_reason if form.is_blocked else None,
    ))
    audit(connection, store, actor, "slot_block_changed", "time_slots", slot_id)


def availability(connection, store, term_id, instructor_id):
    slots = store["time_slots"]
    records = store["instructor_availability"]
    return connection.execute(select(slots, func.coalesce(records.c.is_available, True).label("is_available")).outerjoin(
        records, (records.c.instructor_id == instructor_id) & (records.c.slot_id == slots.c.slot_id)
    ).where(slots.c.term_id == term_id).order_by(slots.c.day_of_week, slots.c.slot_index)).mappings().all()


def set_availability(connection, store, actor, instructor_id, slot_id, is_available):
    slot = by_id(connection, store["time_slots"], slot_id)
    ensure_editable(by_id(connection, store["academic_terms"], slot["term_id"], lock=True))
    table = store["instructor_availability"]
    pair = (table.c.instructor_id == instructor_id, table.c.slot_id == slot_id)
    if is_available:
        connection.execute(table.delete().where(*pair))
    elif connection.execute(table.update().where(*pair).values(is_available=False)).rowcount == 0:
        connection.execute(table.insert().values(instructor_id=instructor_id, slot_id=slot_id, is_available=False))
    audit(connection, store, actor, "availability_changed", "instructors", instructor_id, str(slot_id))


def demand(course, slot_minutes):
    lecture, overflow_lecture = divmod(course["lecture_hours"] * 60, slot_minutes)
    lab, overflow_lab = divmod(course["lab_hours"] * 60, slot_minutes)
    if overflow_lecture or overflow_lab:
        raise ValueError("Contact hours do not fit the slot length. Adjust the course hours or the grid.")
    return {"lecture_slots": lecture, "lab_slots": lab}

