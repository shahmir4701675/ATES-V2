"""CSV preview, natural-key references and guarded, atomic confirmation."""

import csv
from hashlib import sha256
from io import StringIO

from pydantic import ValidationError
from sqlalchemy import select

from backend.api import master_schemas as forms
from backend.api.errors import problem
from backend.services import master
from backend.services.security import audit

MB_10 = 10 * 1024 * 1024
CsvTypes = {
    "courses": (forms.Course, {
        "course_code": "CS101", "title": "Introduction to Computing", "department_code": "CS",
        "credit_hours": "3", "lecture_hours": "2", "lab_hours": "1",
    }),
    "instructors": (forms.Instructor, {
        "full_name": "Amina Khan", "department_code": "CS", "email": "amina@example.test",
        "max_daily_hours": "4", "max_weekly_hours": "18",
    }),
    "rooms": (forms.Room, {"room_code": "R101", "building": "Main", "capacity": "35", "room_type": "Lecture"}),
    "batches": (forms.Batch, {
        "department_code": "CS", "program_code": "CS", "batch_year": "2026", "section": "A", "strength": "30",
    }),
    "offerings": (forms.Offering, {
        "term_name": "Spring 2027", "course_code": "CS101", "program_code": "CS", "batch_year": "2026",
        "section": "A", "instructor_email": "amina@example.test", "enrolled_count": "30",
    }),
    "enrollments": (forms.Enrollment, {
        "term_name": "Spring 2027", "course_code": "CS101", "program_code": "CS", "batch_year": "2026",
        "section": "A", "student_username": "student1",
    }),
}


def rows_for(connection, store, name):
    return connection.execute(select(store[name])).mappings()


def indexes(connection, store, entity):
    result = {}
    if entity in {"courses", "instructors", "batches"}:
        result["department_code"] = {row["code"]: row["department_id"] for row in rows_for(connection, store, "departments")}
    if entity in {"offerings", "enrollments"}:
        result["term_name"] = {row["name"]: row["term_id"] for row in rows_for(connection, store, "academic_terms")
                               if row["status"] != "Closed"}
        result["course_code"] = {row["course_code"]: row["course_id"] for row in rows_for(connection, store, "courses")
                                 if row["is_active"] or entity == "enrollments"}
        result["batch"] = {(row["program_code"], str(row["batch_year"]), row["section"]): row["batch_id"]
                           for row in rows_for(connection, store, "batches") if row["is_active"] or entity == "enrollments"}
    if entity == "offerings":
        result["instructor_email"] = {row["email"]: row["instructor_id"] for row in rows_for(connection, store, "instructors")
                                       if row["is_active"]}
    if entity == "enrollments":
        users = store["users"]
        result["student_username"] = dict(connection.execute(select(users.c.username, users.c.user_id)
                                             .where(users.c.role == "Student")).all())
        result["offering"] = {(row["term_id"], row["course_id"], row["batch_id"]): row["offering_id"]
                              for row in rows_for(connection, store, "course_offerings")}
    resource = master.RESOURCES[entity]
    result["used"] = {tuple(row[key] for key in resource.unique) for row in rows_for(connection, store, resource.table)}
    return result


def convert(entity, values, references):
    issues = []

    def resolve(column, key):
        found = references[column].get(key)
        if found is None:
            issues.append((column, "No matching eligible record."))
        return found

    data = values.copy()
    if "department_code" in data:
        data["department_id"] = resolve("department_code", data.pop("department_code"))
    if entity in {"offerings", "enrollments"}:
        term_id = resolve("term_name", data.pop("term_name"))
        course_id = resolve("course_code", data.pop("course_code"))
        batch_id = resolve("batch", tuple(data.pop(key) for key in ("program_code", "batch_year", "section")))
        if entity == "offerings":
            data.update(term_id=term_id, course_id=course_id, batch_id=batch_id,
                        instructor_id=resolve("instructor_email", data.pop("instructor_email")))
        else:
            offering_id = resolve("offering", (term_id, course_id, batch_id)) if not issues else None
            data.update(offering_id=offering_id, student_id=resolve("student_username", data.pop("student_username")))
    if issues:
        return None, issues
    schema = CsvTypes[entity][0]
    try:
        converted = schema.model_validate(data).model_dump(exclude={"department", "confirm_deactivate"})
    except ValidationError as exc:
        return None, [(".".join(map(str, item["loc"])) or "row", item["msg"]) for item in exc.errors()]
    unique = master.RESOURCES[entity].unique
    key = tuple(converted[field] for field in unique)
    if key in references["used"]:
        return None, [(unique[-1], "This record already exists in the file or database.")]
    references["used"].add(key)
    return converted, []


def summarize(entity, source, reference_data):
    try:
        content = source.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise problem(422, "Save the CSV file as UTF-8 and upload it again.", "file") from None
    reader = csv.reader(StringIO(content, newline=""), strict=True)
    expected = CsvTypes[entity][1]
    try:
        header = [item.strip() for item in next(reader, [])]
        if len(header) != len(expected) or set(header) != set(expected):
            raise problem(422, "Use the template headers for this import type.", "file")
        line = 2
        valid = []
        rejects = []
        total = 0
        for fields in reader:
            if fields and any(value.strip() for value in fields):
                total += 1
                if len(fields) != len(header):
                    rejects.append({"line": line, "issues": [{"column": "row", "reason": "The number of columns differs from the header."}]})
                else:
                    values = {key: value.strip() for key, value in zip(header, fields)}
                    missing = [(key, "A value is required.") for key, value in values.items() if not value]
                    _, issues = (None, missing) if missing else convert(entity, values, reference_data)
                    if issues:
                        rejects.append({"line": line, "issues": [{"column": column, "reason": reason} for column, reason in issues]})
                    else:
                        valid.append(values)
            line = reader.line_num + 1
    except (csv.Error, ValueError) as exc:
        raise problem(422, f"The CSV cannot be read near line {reader.line_num}: {exc}", "file") from None
    if not total:
        raise problem(422, "The CSV has a header and no data rows.", "file")
    return {"total": total, "valid": valid, "rejected": rejects}


def batch_view(row):
    preview = row["preview"]
    return {"key": row["import_key"], "state": row["state"], "entity": row["entity"],
            "filename": row["filename"], "total": preview["total"], "valid_count": len(preview["valid"]),
            "rejected": preview["rejected"]}


def preview(connection, store, actor, key, entity, filename, source):
    master.serialize_term_change(connection)
    table = store["staged_imports"]
    digest = sha256(source).hexdigest()
    prior = connection.execute(select(table).where(table.c.import_key == key)).mappings().first()
    if prior:
        if prior["user_id"] == actor and (prior["content_hash"], prior["entity"], prior["filename"]) == (digest, entity, filename):
            return batch_view(prior)
        raise problem(409, "This import identifier is already in use.")
    validated = summarize(entity, source, indexes(connection, store, entity))
    row = connection.execute(table.insert().values(
        import_key=key, user_id=actor, entity=entity, filename=filename, content_hash=digest,
        state="Pending", preview=validated,
    ).returning(*table.c)).mappings().one()
    return batch_view(row)


def apply(connection, store, actor, key, confirm):
    master.serialize_term_change(connection)
    table = store["staged_imports"]
    record = connection.execute(select(table).where(table.c.import_key == key, table.c.user_id == actor)
                                .with_for_update()).mappings().first()
    if not record:
        raise problem(404, "This import preview could not be found.")
    if record["state"] != "Pending":
        return batch_view(record)
    entity = record["entity"]
    preview = record["preview"]
    if confirm:
        if not preview["valid"]:
            raise problem(422, "There are no valid rows to import.")
        reference_data = indexes(connection, store, entity)
        rows = []
        for values in preview["valid"]:
            row, issues = convert(entity, values, reference_data)
            if issues:
                raise problem(409, "The database changed after validation. Upload the file again to check its rows.")
            rows.append(row)
        target = store[master.RESOURCES[entity].table]
        connection.execute(target.insert(), rows)
        connection.execute(store["import_logs"].insert().inline().values(
            user_id=actor, entity_type=entity, file_name=record["filename"],
            rows_total=preview["total"], rows_imported=len(rows), rows_rejected=len(preview["rejected"]),
        ))
    state = "Confirmed" if confirm else "Cancelled"
    connection.execute(table.update().where(table.c.import_key == key).values(state=state))
    audit(connection, store, actor, "import_confirmed" if confirm else "import_cancelled", "Import",
          details=f"{entity}: {record['filename']}")
    return batch_view(dict(record, state=state))

