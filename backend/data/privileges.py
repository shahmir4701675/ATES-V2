"""Grants for a dedicated, existing, non-owner PostgreSQL runtime login."""

from backend.data.database import check_disposable

# These privileges cover the Phase 1 API. Expand them alongside feature migrations.
PHASE_ONE_ACCESS = {
    "departments": "SELECT, INSERT",
    "instructors": "SELECT, INSERT",
    "batches": "SELECT, INSERT",
    "users": "SELECT, INSERT, UPDATE",
    "user_sessions": "SELECT, INSERT, UPDATE, DELETE",
    "audit_logs": "INSERT",
}

API_ACCESS = {
    **PHASE_ONE_ACCESS,
    "audit_logs": "SELECT, INSERT",
    "departments": "SELECT, INSERT, UPDATE",
    "instructors": "SELECT, INSERT, UPDATE",
    "batches": "SELECT, INSERT, UPDATE",
    "academic_terms": "SELECT, INSERT, UPDATE",
    "courses": "SELECT, INSERT, UPDATE",
    "rooms": "SELECT, INSERT, UPDATE",
    "time_slots": "SELECT, INSERT, UPDATE, DELETE",
    "instructor_availability": "SELECT, INSERT, UPDATE, DELETE",
    "course_offerings": "SELECT, INSERT, UPDATE",
    "enrollments": "SELECT, INSERT, DELETE",
    "scheduling_configs": "SELECT, INSERT, UPDATE, DELETE",
    "constraint_rules": "SELECT, INSERT, UPDATE",
    "exam_slots": "SELECT, INSERT, UPDATE",
    "schedules": "SELECT, INSERT, UPDATE",
    "timetable_entries": "SELECT, INSERT, UPDATE, DELETE",
    "exam_entries": "SELECT, INSERT, UPDATE",
    "exam_room_allocations": "SELECT, INSERT, DELETE",
    "term_exam_exclusions": "SELECT, INSERT, DELETE",
    "schedule_runs": "SELECT, INSERT, UPDATE",
    "conflict_log": "SELECT, INSERT",
    "staged_imports": "SELECT, INSERT, UPDATE",
    "import_logs": "INSERT",
}
WORKER_ACCESS = {
    "schedules": "SELECT, UPDATE",
    "schedule_runs": "SELECT, UPDATE",
    "timetable_entries": "INSERT",
    "exam_entries": "SELECT, INSERT",
    "exam_room_allocations": "INSERT",
    "rooms": "SELECT",
    "conflict_log": "INSERT",
    "audit_logs": "INSERT",
}
PROFILES = {"access": PHASE_ONE_ACCESS, "api": API_ACCESS, "worker": WORKER_ACCESS}


def grant_local_runtime(engine, role, profile="access"):
    check_disposable(engine.url)
    if engine.dialect.name != "postgresql":
        raise ValueError("Runtime roles require PostgreSQL.")
    name = engine.dialect.identifier_preparer.quote_identifier(role)
    with engine.begin() as connection:
        attributes = connection.exec_driver_sql(
            "SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = %s",
            (role,),
        ).one_or_none()
        if attributes != (True, False, False, False, False):
            raise ValueError("Use a dedicated login with no elevated PostgreSQL role attributes.")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {name}")
        for table, rights in PROFILES[profile].items():
            connection.exec_driver_sql(f"GRANT {rights} ON TABLE public.{table} TO {name}")
            statements = {
                "SELECT": "USING (true)",
                "INSERT": "WITH CHECK (true)",
                "UPDATE": "USING (true) WITH CHECK (true)",
                "DELETE": "USING (true)",
            }
            for command in rights.split(", "):
                policy = engine.dialect.identifier_preparer.quote_identifier(
                    f"{profile}_{command.lower()}_{role}"[:63]
                )
                connection.exec_driver_sql(f"DROP POLICY IF EXISTS {policy} ON public.{table}")
                connection.exec_driver_sql(
                    f"CREATE POLICY {policy} ON public.{table} FOR {command} TO {name} {statements[command]}"
                )

