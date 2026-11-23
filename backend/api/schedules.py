"""Timetable generation and the version browser."""

from datetime import date as CalendarDate
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, StringConstraints
from sqlalchemy import select

from backend.api.errors import problem
from backend.api.master import require_role
from backend.api.schemas import AccountId, Input
from backend.services import schedule_views, scheduling, versions as version_service
from backend.services.csv_output import csv_text
from backend.services.exam_scheduling import set_examinable
from backend.services.exports import CsvExporter, PdfExporter
from backend.services.security import audit


class Generation(Input):
    term_id: AccountId
    request_token: UUID
    config_id: AccountId | None = None
    source_id: AccountId | None = None
    schedule_type: Literal["Timetable", "Exam"] = "Timetable"


class ExamInclusion(Input):
    included: bool


class Revision(Input):
    revision: Annotated[int, Field(ge=1)]


class EntryChange(Revision):
    entry: Annotated[str, StringConstraints(min_length=1, max_length=48)]


class Move(EntryChange):
    slot_id: AccountId
    room_id: AccountId | None = None
    seats: Annotated[dict[AccountId, Annotated[int, Field(ge=1, le=32767)]], Field(min_length=1, max_length=300)] | None = None


class Lock(EntryChange):
    locked: bool


class Approval(Revision):
    replace_id: AccountId | None = None
    confirmed: bool


class ScheduleFilters(Input):
    room: AccountId | None = None
    course: AccountId | None = None
    instructor: AccountId | None = None
    batch: AccountId | None = None
    day: Annotated[int, Field(ge=1, le=7)] | None = None
    date: CalendarDate | None = None


def register_schedules(app, Current):
    Filters = Annotated[ScheduleFilters, Depends()]

    def read(request, context, key):
        connection, actor, _ = context
        store = request.app.state.store
        schedule, details = scheduling.get_schedule(connection, store, key)
        version_service.readable(actor, schedule)
        return connection, store, schedule, details

    @app.get("/schedules/published", tags=["Schedules"])
    def published(request: Request, context: Current, schedule_type: Literal["Timetable", "Exam"],
                  term_id: Annotated[int | None, Query(ge=1, le=2147483647)] = None):
        connection, _, _ = context
        store = request.app.state.store
        terms = store["academic_terms"]
        table = store["schedules"]
        candidates = connection.execute(select(terms.c.term_id, terms.c.name, table.c.schedule_id).join(table).where(
            table.c.status == "Published", table.c.schedule_type == schedule_type,
        ).order_by(terms.c.start_date.desc(), terms.c.term_id)).mappings().all()
        if term_id and not any(row["term_id"] == term_id for row in candidates):
            raise problem(404, "No published schedule is available for this term.")
        target = terms.c.term_id == term_id if term_id else terms.c.status == "Active"
        term = connection.execute(select(terms.c.term_id, terms.c.name).where(target)).first()
        if not term:
            return {"term_name": None, "schedule_id": None, "terms": candidates}
        schedule = next((row for row in candidates if row["term_id"] == term.term_id), None)
        return {"term_name": term.name, "term_id": term.term_id,
                "schedule_id": schedule["schedule_id"] if schedule else None, "terms": candidates}

    @app.get("/schedules", tags=["Schedules"])
    def versions(request: Request, context: Current, term_id: Annotated[int, Query(ge=1, le=2147483647)],
                 schedule_type: Literal["Timetable", "Exam"] | None = None):
        connection, actor, _ = context
        require_role(actor, "Coordinator", "Approver")
        store = request.app.state.store
        table = store["schedules"]
        runs = store["schedule_runs"]
        query = select(table, runs.c.outcome).outerjoin(runs).where(table.c.term_id == term_id)
        if schedule_type:
            query = query.where(table.c.schedule_type == schedule_type)
        query = query.order_by(table.c.generated_at.desc(), table.c.schedule_id.desc())
        return connection.execute(query.limit(100)).mappings().all()

    @app.post("/schedules/generate", status_code=202, tags=["Schedules"])
    def generate(request: Request, context: Current, form: Generation, response: Response):
        connection, actor, _ = context
        require_role(actor, "Coordinator")
        store = request.app.state.store
        row = scheduling.submit(connection, store, actor["user_id"], form)
        if row["status"] == "Draft":
            response.status_code = 201
        return row

    @app.get("/schedules/{schedule_id}/status", tags=["Schedules"])
    def run_status(request: Request, context: Current, schedule_id: int):
        _, _, schedule, details = read(request, context, schedule_id)
        result = scheduling.run_summary(schedule, details)
        if context[1]["role"] not in version_service.STAFF:
            return {key: result[key] for key in ("schedule_id", "schedule_type", "version_no", "status", "term_name") if key in result}
        return result

    @app.post("/schedules/{schedule_id}/cancel", tags=["Schedules"])
    def cancel(request: Request, context: Current, schedule_id: int):
        connection, actor, _ = context
        require_role(actor, "Coordinator")
        return scheduling.stop_run(connection, request.app.state.store, actor["user_id"], schedule_id)

    @app.get("/schedules/{schedule_id}/entries", tags=["Schedules"])
    def entries(request: Request, context: Current, schedule_id: int, filters: Filters):
        connection, store, schedule, details = read(request, context, schedule_id)
        if schedule["status"] not in {"Generated", "Published", "Archived"}:
            raise problem(409, "This version does not have saved entries.")
        return JSONResponse(schedule_views.filtered_view(connection, store, context[1], schedule, details, filters))

    @app.get("/schedules/{schedule_id}/export", tags=["Schedules"])
    def export(request: Request, context: Current, schedule_id: int, filters: Filters,
               format: Literal["pdf", "csv"], group_by: Literal["batch", "instructor"] | None = None):
        connection, store, schedule, details = read(request, context, schedule_id)
        if schedule["status"] not in {"Generated", "Published", "Archived"}:
            raise problem(409, "Only versions with saved entries can be exported.")
        actor = context[1]
        if group_by:
            require_role(actor, "Coordinator")
            if format != "pdf":
                raise problem(422, "Grouped exports are available in PDF.")
        payload = schedule_views.filtered_view(connection, store, actor, schedule, details, filters)
        rows = list(schedule_views.logical_rows(schedule, payload))
        if format == "csv":
            exporter = CsvExporter()
            data = exporter.render(rows)
        else:
            term = details["input_snapshot"]["term_name"] if details else "Academic term"
            selected = filters.model_dump(exclude_none=True)
            label = "All visible entries"
            if selected:
                label = "Filters · " + " · ".join(f"{key}: {value}" for key, value in selected.items())
            exporter = PdfExporter(schedule, term, label)
            data = exporter.render(rows, group_by)
        audit(connection, store, actor["user_id"], "schedule_exported", "Schedule", schedule_id,
              format + (f" grouped by {group_by}" if group_by else ""))
        filename = f"ates-{schedule['schedule_type'].lower()}-v{schedule['version_no']}.{exporter.extension}"
        return Response(data, media_type=exporter.media_type, headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        })

    @app.put("/schedules/{schedule_id}/entries", tags=["Schedules"])
    def move_entry(request: Request, context: Current, schedule_id: int, form: Move):
        require_role(context[1], "Coordinator")
        return version_service.move(context[0], request.app.state.store, context[1]["user_id"], schedule_id, form)

    @app.put("/schedules/{schedule_id}/locks", tags=["Schedules"])
    def lock_entry(request: Request, context: Current, schedule_id: int, form: Lock):
        require_role(context[1], "Coordinator")
        return version_service.lock_entry(context[0], request.app.state.store, context[1]["user_id"], schedule_id, form)

    @app.post("/schedules/{schedule_id}/undo", tags=["Schedules"])
    def undo_entries(request: Request, context: Current, schedule_id: int, form: Revision):
        require_role(context[1], "Coordinator")
        return version_service.undo(context[0], request.app.state.store, context[1]["user_id"], schedule_id, form.revision)

    @app.get("/schedules/{schedule_id}/review", tags=["Schedules"])
    def review_schedule(request: Request, context: Current, schedule_id: int):
        require_role(context[1], "Approver")
        return version_service.review(context[0], request.app.state.store, schedule_id)

    @app.post("/schedules/{schedule_id}/publish", tags=["Schedules"])
    def publish_schedule(request: Request, context: Current, schedule_id: int, form: Approval):
        require_role(context[1], "Approver")
        return version_service.publish(context[0], request.app.state.store, context[1]["user_id"], schedule_id, form)

    @app.post("/schedules/{schedule_id}/duplicate", status_code=201, tags=["Schedules"])
    def duplicate_schedule(request: Request, context: Current, schedule_id: int, form: Revision):
        require_role(context[1], "Coordinator")
        return version_service.duplicate(context[0], request.app.state.store, context[1]["user_id"], schedule_id, form.revision)

    @app.post("/schedules/{schedule_id}/validate-draft", tags=["Schedules"])
    def validate_draft(request: Request, context: Current, schedule_id: int, form: Revision):
        require_role(context[1], "Coordinator")
        return version_service.verify_copy(context[0], request.app.state.store, context[1]["user_id"], schedule_id, form.revision)

    @app.get("/terms/{term_id}/exam-courses", tags=["Exam sessions"])
    def exam_courses(request: Request, context: Current, term_id: int):
        connection, actor, _ = context
        require_role(actor, "Coordinator")
        store = request.app.state.store
        courses = store["courses"]
        offerings = store["course_offerings"]
        exclusions = store["term_exam_exclusions"]
        excluded = select(exclusions.c.course_id).where(exclusions.c.term_id == term_id)
        return connection.execute(select(
            courses.c.course_id, courses.c.course_code, courses.c.title, courses.c.course_id.not_in(excluded).label("included"),
        ).where(courses.c.course_id.in_(select(offerings.c.course_id).where(offerings.c.term_id == term_id)))
            .order_by(courses.c.course_code)).mappings().all()

    @app.put("/terms/{term_id}/exam-courses/{course_id}", status_code=204, tags=["Exam sessions"])
    def exam_course_inclusion(request: Request, context: Current, term_id: int, course_id: int, form: ExamInclusion):
        connection, actor, _ = context
        require_role(actor, "Coordinator")
        set_examinable(connection, request.app.state.store, actor["user_id"], term_id, course_id, form.included)
        return Response(status_code=204)

    @app.get("/schedules/{schedule_id}/conflicts", tags=["Schedules"])
    def conflicts(request: Request, context: Current, schedule_id: int, format: Literal["json", "csv"] = "json",
                  conflict_type: Annotated[str | None, Query(max_length=30)] = None):
        require_role(context[1], "Coordinator", "Approver")
        connection, store, _, _ = read(request, context, schedule_id)
        table = store["conflict_log"]
        query = select(table).where(table.c.schedule_id == schedule_id)
        if conflict_type:
            query = query.where(table.c.conflict_type == conflict_type)
        rows = connection.execute(query.order_by(table.c.conflict_id)).mappings().all()
        if format == "csv":
            audit(connection, store, context[1]["user_id"], "conflicts_exported", "Schedule", schedule_id,
                  conflict_type)
            columns = ("conflict_type", "severity", "entity_ref", "description")
            return Response(csv_text([columns, *(tuple(row[key] for key in columns) for row in rows)]),
                            media_type="text/csv", headers={
                                "Content-Disposition": f'attachment; filename="ates-conflicts-{schedule_id}.csv"',
                            })
        return rows

