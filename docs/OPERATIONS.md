# ATES operations and data stewardship

## Start and recover

Follow the platform commands in [README](../README.md). Store the JWT signing secret and all credentials in the process environment. The local HTTPS profile binds to loopback. The institution's deployment needs a trusted certificate, HTTPS on port 443, and a database connection on a private or encrypted channel. The browser uses its own origin for API calls by default. Set `ATES_FRONTEND_ORIGIN` only when a separate authorized frontend origin is required.

Set `ATES_BACKUP_DIRECTORY` to launch daily backups at or after 19:00 Asia/Karachi while the local server is running. The launcher keeps the latest seven generated copies per engine in that directory. PostgreSQL requires matching `pg_dump` and `pg_restore` client tools on PATH or under `ATES_PG_BIN` and the owner connection under `ATES_MIGRATION_DATABASE_URL`. Preserve the API and worker logins separately. Use a restricted backup directory. Avoid sharing database copies through ordinary schedule downloads.

Run `python -m backend.cli backup --directory <directory>` for an on-demand backup. Set the database URL to a fresh disposable destination and run `python -m backend.cli restore <backup>`. On PostgreSQL, create the destination and any roles named by its policies first, then reapply the runtime grants. Start against the restored database and compare the active term, schedule versions, assignments, audit history and settings before accepting a recovery.

On an independent host, run `python -m backend.monitor --workdays 1,2,3,4,5 probe <HTTPS URL>` to record one HTTPS UI check per minute between 08:00 and 18:00 Asia/Karachi. Use `--ca-file` after the probe URL for a local certificate and configure the institution's actual working days. Use `python -m backend.monitor report YYYY-MM` with the same working days and log. A report with missing observations leaves the uptime percentage unset. Keep deployment maintenance outside working hours and verify protected API workflows as part of the operational audit.

## Privacy and access

| Data | Operational use | Access |
| --- | --- | --- |
| Username, full name, email and role | Sign in, administer access and identify an actor in audit | Account owner and Administrator |
| Faculty instructor link and availability | Schedule classes and apply teaching limits | Faculty own availability, Coordinator term-wide |
| Student batch link and offering enrollment | Derive exam conflicts and candidate counts | Account administration and authorized master-data operations |
| Schedule and exam rooms | Inform teaching and exams, including room allocation | Staff version scope, Faculty own assignments, Student own batch, Administrator published scope |
| Password hashes, session IDs and input snapshots | Authenticate users, invalidate sessions and reproduce versions | Backend storage with restricted database access |
| Audit and import history | Review actions and reconcile changes | Administrator audit view and restricted database retention |

Schedule exports follow the same scoped records and active filters as the browser. They are recorded in the audit log. Protect exports with the same access rules as the corresponding printed timetable. The university's retention, records-access and destruction rules still require institutional review.

## Reuse boundaries

- `backend/engine/timetable_data.py` and `backend/engine/exam_data.py` define the immutable run input and logical assignments. Call the solvers and validators without importing FastAPI. The reference benchmark builds repeatable fixtures.
- `backend/services/imports.py` defines the six UTF-8 templates and import validation. `backend/services/schedule_views.py` shapes scoped displays and export rows. Use [the CSV field guide](CSV_FIELDS.md) for a second department.
- `docs/SUPABASE_CATALOG.json` records the 21 business relations and their original keys, constraints and indexes. The versioned migrations under `migrations/` are the executable data dictionary. Supporting tables track sessions, generation snapshots, CSV previews and exam exclusions.
- Browse **API reference** as Administrator. The OpenAPI JSON and interactive requests use the authenticated session. Local tools can authenticate through `POST /auth/login` and attach the JWT as an Authorization Bearer header.

## Third-party components

ATES uses FastAPI, Starlette, SQLAlchemy, Alembic, Uvicorn, bcrypt, PyJWT, Cryptography, Psycopg, OR-Tools, NetworkX, ReportLab, React, Tailwind CSS, Swagger UI and Vite. The runtime pins are in the requirements files and browser lockfile. Refer to [third-party notices](THIRD_PARTY_NOTICES.txt) for the installed build. Run `python docs/build_notices.py` from the platform used to prepare another distribution. Fonts used in PDF output come from the server unless an operator supplies a permitted TrueType font through `ATES_PDF_FONT`.

