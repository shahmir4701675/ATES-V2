"""Master data and availability HTTP endpoints."""

from typing import Annotated

from fastapi import Query, Request, Response
from sqlalchemy import select

from backend.api import master_schemas as schemas
from backend.api.errors import problem
from backend.services import master

ROUTES = {
    "departments": schemas.Department, "terms": schemas.Term, "courses": schemas.Course,
    "instructors": schemas.Instructor, "rooms": schemas.Room, "batches": schemas.Batch,
    "offerings": schemas.Offering, "enrollments": schemas.Enrollment,
}


def require_role(user, *roles):
    if user["role"] not in roles:
        raise problem(403, "Your role does not have access to this operation.")


def register_master(app, Current):
    def routes_for(resource, Form):
        def list_records(
            request: Request, context: Current, term_id: int | None = None,
            search: Annotated[str, Query(max_length=150)] = "",
            sort: Annotated[str, Query(max_length=50)] | None = None,
            descending: bool = False,
            page: Annotated[int, Query(ge=1, le=100_000)] = 1,
        ):
            connection, actor, _ = context
            require_role(actor, "Coordinator", "Approver")
            return master.list_records(connection, request.app.state.store, resource, term_id, search, sort,
                                       descending, page)

        def create(request: Request, context: Current, form: Form):
            connection, actor, _ = context
            require_role(actor, "Coordinator")
            return master.save_record(connection, request.app.state.store, actor["user_id"], resource, form)

        def update(request: Request, context: Current, item_id: int, form: Form):
            connection, actor, _ = context
            require_role(actor, "Coordinator")
            return master.save_record(connection, request.app.state.store, actor["user_id"], resource, form, item_id)

        app.add_api_route(f"/{resource}", list_records, name=f"List {resource}", methods=["GET"], tags=["Master data"])
        app.add_api_route(f"/{resource}", create, name=f"Create {resource}", methods=["POST"],
                          status_code=201, tags=["Master data"])
        if resource != "enrollments":
            app.add_api_route(f"/{resource}/{{item_id}}", update, name=f"Update {resource}", methods=["PUT"],
                              tags=["Master data"])

    for resource, schema in ROUTES.items():
        routes_for(resource, schema)

    @app.get("/api/master/references", tags=["Master data"])
    def master_references(request: Request, context: Current, term_id: int | None = None):
        connection, actor, _ = context
        require_role(actor, "Coordinator", "Approver", "Faculty")
        store = request.app.state.store
        terms = store["academic_terms"]
        result = {"terms": connection.execute(select(terms).order_by(
            (terms.c.status == "Active").desc(), terms.c.start_date.desc(),
        )).mappings().all()}
        if actor["role"] == "Faculty":
            return result
        for key in ("departments", "courses", "batches", "instructors", "course_offerings"):
            table = store[key]
            query = select(table)
            if key == "course_offerings" and term_id:
                query = query.where(table.c.term_id == term_id)
            result[key] = connection.execute(query.order_by(next(iter(table.primary_key)))).mappings().all()
        users = store["users"]
        result["students"] = connection.execute(select(users.c.user_id, users.c.full_name, users.c.username).where(
            users.c.role == "Student",
        ).order_by(users.c.full_name, users.c.user_id)).mappings().all()
        return result

    @app.get("/terms/{term_id}/grid", tags=["Weekly grid"])
    def grid(request: Request, context: Current, term_id: int):
        require_role(context[1], "Coordinator", "Approver")
        store = request.app.state.store
        master.by_id(context[0], store["academic_terms"], term_id)
        return master.slot_rows(context[0], store, term_id)

    @app.put("/terms/{term_id}/grid", tags=["Weekly grid"])
    def save_grid(request: Request, context: Current, term_id: int, form: schemas.Grid):
        require_role(context[1], "Coordinator")
        return master.save_grid(context[0], request.app.state.store, context[1]["user_id"], term_id, form)

    @app.put("/slots/{slot_id}/block", status_code=204, tags=["Weekly grid"])
    def update_block(request: Request, context: Current, slot_id: int, form: schemas.Block):
        require_role(context[1], "Coordinator")
        master.set_block(context[0], request.app.state.store, context[1]["user_id"], slot_id, form)
        return Response(status_code=204)

    @app.delete("/enrollments/{enrollment_id}", status_code=204, tags=["Master data"])
    def delete_enrollment(request: Request, context: Current, enrollment_id: int):
        require_role(context[1], "Coordinator")
        master.remove_enrollment(context[0], request.app.state.store, context[1]["user_id"], enrollment_id)
        return Response(status_code=204)

    def scope_instructor(user, instructor_id):
        require_role(user, "Coordinator", "Faculty")
        if user["role"] == "Faculty":
            if instructor_id is not None and instructor_id != user["instructor_id"]:
                raise problem(403, "Faculty can only access their own availability.")
            return user["instructor_id"]
        if instructor_id is None:
            raise problem(422, "Select an instructor.", "instructor_id")
        return instructor_id

    @app.get("/availability/{term_id}", tags=["Availability"])
    def get_availability(request: Request, context: Current, term_id: int, instructor_id: int | None = None):
        actor = context[1]
        instructor_id = scope_instructor(actor, instructor_id)
        store = request.app.state.store
        master.by_id(context[0], store["academic_terms"], term_id)
        master.by_id(context[0], store["instructors"], instructor_id)
        return master.availability(context[0], store, term_id, instructor_id)

    @app.put("/availability/slots/{slot_id}", status_code=204, tags=["Availability"])
    def set_availability(request: Request, context: Current, slot_id: int, form: schemas.Availability,
                         instructor_id: int | None = None):
        actor = context[1]
        instructor_id = scope_instructor(actor, instructor_id)
        store = request.app.state.store
        master.by_id(context[0], store["instructors"], instructor_id)
        master.set_availability(context[0], store, actor["user_id"], instructor_id, slot_id, form.is_available)
        return Response(status_code=204)

