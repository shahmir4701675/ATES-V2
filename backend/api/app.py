"""FastAPI application and same-origin browser entry point."""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.api.errors import problem, validation_response
from backend.api.audit import register_audit
from backend.api.imports import register_imports
from backend.api.master import register_master
from backend.api.schedules import register_schedules
from backend.api.settings import register_settings
from backend.api.upload_limit import UploadLimit
from backend.api.schemas import AccountDetails, AccountStatus, ChangePassword, Login, NewAccount, ResetPassword
from backend.data.database import ROOT
from backend.data.store import Store
from backend.services import accounts
from backend.services.security import Security, audit, utc_now, verify_password

bearer = HTTPBearer(auto_error=False)
DIST = ROOT / "frontend" / "dist"


def create_app(database_url=None, secret=None, clock=utc_now):
    database_url = database_url or os.environ["ATES_DATABASE_URL"]
    secret = secret or os.environ["ATES_JWT_SECRET"]
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("Set ATES_JWT_SECRET to a random value of at least 32 bytes.")

    @asynccontextmanager
    async def lifespan(app):
        store = Store(database_url)
        app.state.store = store
        app.state.security = Security(store, secret, clock)
        try:
            yield
        finally:
            store.engine.dispose()

    app = FastAPI(
        title="Auto Timetable / Exam Scheduler", version="0.1.0",
        docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan,
    )
    app.add_exception_handler(RequestValidationError, validation_response)
    app.add_middleware(UploadLimit)
    configured_origin = os.environ.get("ATES_FRONTEND_ORIGIN")
    if configured_origin:
        app.add_middleware(CORSMiddleware, allow_origins=[configured_origin],
                           allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if not request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(
            status_code=409,
            content={"detail": {"message": "The requested change conflicts with existing data. Check the values and retry.", "fields": {}}},
        )

    def current(request: Request, credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if not credential:
            raise problem(401, "Sign in to continue.")
        store = request.app.state.store
        security = request.app.state.security
        path = request.url.path
        audited_download = path.endswith("/export") or (
            path.endswith("/conflicts") and request.query_params.get("format") == "csv"
        )
        if request.method != "GET" or audited_download:
            with store.transaction() as connection:
                user, session_id = security.authenticate(connection, credential.credentials)
                yield connection, user, session_id
        else:
            polling = path.startswith("/schedules/") and path.endswith("/status")
            with store.transaction(write=not polling) as connection:
                user, session_id = security.authenticate(connection, credential.credentials, activity=not polling)
            with store.transaction(write=False) as connection:
                yield connection, user, session_id

    Current = Annotated[tuple, Depends(current, scope="function")]

    def administrator(context: Current):
        if context[1]["role"] != "Administrator":
            raise problem(403, "Only Administrators can manage user accounts.")
        return context

    Admin = Annotated[tuple, Depends(administrator)]

    @app.post("/auth/login", tags=["Authentication"])
    def login(request: Request, form: Login):
        with request.app.state.store.transaction() as connection:
            result = request.app.state.security.login(connection, form.username, form.password)
        if isinstance(result, Exception):
            raise result
        return result

    @app.get("/auth/session", tags=["Authentication"])
    def session(context: Current):
        return accounts.public_user(context[1])

    @app.post("/auth/logout", status_code=204, tags=["Authentication"])
    def logout(request: Request, context: Current):
        connection, user, sid = context
        store = request.app.state.store
        sessions = store["user_sessions"]
        connection.execute(sessions.delete().where(sessions.c.session_id == sid))
        audit(connection, store, user["user_id"], "logout", entity_id=user["user_id"])
        return Response(status_code=204)

    @app.put("/auth/password", status_code=204, tags=["Authentication"])
    def change_password(request: Request, context: Current, form: ChangePassword):
        connection, user, _ = context
        if not verify_password(form.current_password, user["password_hash"]):
            raise problem(422, "The current password is incorrect.", "current_password")
        accounts.set_password(connection, request.app.state.store, user["user_id"], user["user_id"],
                              form.password, "password_changed")
        return Response(status_code=204)

    @app.get("/api/dashboard", tags=["Dashboard"])
    def dashboard(request: Request, context: Current):
        connection, actor, _ = context
        dashboard_data = {"user": accounts.public_user(actor)}
        if actor["role"] in {"Coordinator", "Approver"}:
            store = request.app.state.store
            terms = store["academic_terms"]
            term = connection.execute(select(terms).where(terms.c.status == "Active")).mappings().first()
            dashboard_data["active_term"] = term
            if term:
                slots = store["time_slots"]
                rooms = store["rooms"]
                offerings = store["course_offerings"]
                dashboard_data["counts"] = {
                    "slots": connection.scalar(select(func.count()).select_from(slots).where(
                        slots.c.term_id == term["term_id"], slots.c.is_blocked.is_(False))),
                    "rooms": connection.scalar(select(func.count()).select_from(rooms).where(rooms.c.is_active.is_(True))),
                    "offerings": connection.scalar(select(func.count()).select_from(offerings).where(
                        offerings.c.term_id == term["term_id"])),
                }
                schedules = store["schedules"]
                states = {}
                for kind in ("Timetable", "Exam"):
                    latest = connection.execute(select(schedules).where(
                        schedules.c.term_id == term["term_id"], schedules.c.schedule_type == kind,
                    ).order_by(schedules.c.version_no.desc()).limit(1)).mappings().first()
                    states[kind] = {key: latest[key] for key in ("schedule_id", "version_no", "status")} if latest else None
                dashboard_data["schedules"] = states
        return dashboard_data

    @app.get("/api/users", tags=["Accounts"])
    def list_accounts(request: Request, context: Admin, search: Annotated[str, Query(max_length=120)] = "",
                      page: Annotated[int, Query(ge=1, le=100_000)] = 1):
        return accounts.search_accounts(context[0], request.app.state.store, search, page)

    @app.get("/api/users/references", tags=["Accounts"])
    def references(request: Request, context: Admin):
        store = request.app.state.store
        result = {}
        for entity in ("departments", "instructors", "batches"):
            table = store[entity]
            excluded = {"is_active", "max_daily_hours", "max_weekly_hours", "department_id"} if entity != "departments" else set()
            query = select(*(column for column in table.c if column.name not in excluded))
            if entity != "departments":
                query = query.where(table.c.is_active.is_(True))
            result[entity] = context[0].execute(query.order_by(next(iter(table.primary_key)))).mappings().all()
        return result

    @app.post("/api/users", status_code=201, tags=["Accounts"])
    def create_account(request: Request, context: Admin, form: NewAccount):
        return accounts.save_account(context[0], request.app.state.store, context[1]["user_id"], form)

    @app.put("/api/users/{user_id}", tags=["Accounts"])
    def update_account(request: Request, context: Admin, user_id: int, form: AccountDetails):
        return accounts.save_account(context[0], request.app.state.store, context[1]["user_id"], form, user_id)

    @app.put("/api/users/{user_id}/status", status_code=204, tags=["Accounts"])
    def account_status(request: Request, context: Admin, user_id: int, form: AccountStatus):
        accounts.set_status(context[0], request.app.state.store, context[1]["user_id"], user_id, form.active)
        return Response(status_code=204)

    @app.put("/api/users/{user_id}/password", status_code=204, tags=["Accounts"])
    def reset_password(request: Request, context: Admin, user_id: int, form: ResetPassword):
        accounts.find_account(context[0], request.app.state.store, user_id)
        accounts.set_password(context[0], request.app.state.store, context[1]["user_id"], user_id, form.password,
                              "password_reset")
        return Response(status_code=204)

    @app.get("/openapi.json", include_in_schema=False)
    def openapi(context: Admin):
        return app.openapi()

    register_master(app, Current)
    register_schedules(app, Current)
    register_imports(app, Current)
    register_settings(app, Current)
    register_audit(app, Current)

    @app.get("/", include_in_schema=False)
    def browser_shell():
        if not (DIST / "index.html").is_file():
            raise problem(503, "Build the browser application with npm run build in frontend.")
        return FileResponse(DIST / "index.html")

    if (DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    return app

