# ATES V2

ATES is the Automated Timetable and Examination Scheduling System for one academic department. It helps Administrators and Coordinators prepare terms, generate timetables and exam schedules, and manage revisions. Approvers review and publish schedules. Faculty and Students can open their assigned views and download scoped exports.

## Technology stack

- React, Tailwind CSS and Vite build the browser interface. FastAPI serves that build and the API from the same HTTPS origin.
- SQLAlchemy and Alembic support SQLite for local development and PostgreSQL for deployment. A separate Python worker claims runs from the application database. OR-Tools CP-SAT and NetworkX support timetable and exam scheduling, respectively.

## Install and run locally

Install Git, Python 3.11 or newer, and Node.js 18 or newer with npm. Clone this private repository using an account with access, then open a terminal in the checkout. On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-engine.txt
npm ci --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python -m backend.cli bootstrap --email admin@example.test
.\.venv\Scripts\python -m backend.cli serve
```

On Linux, use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows Python paths. The `npm ci` step installs the locked frontend dependencies. The build writes `frontend/dist`, which the backend serves. Bootstrap prompts for a password and creates the first Administrator. Subsequent startups only need the final command, which starts FastAPI and the solver worker. Open [ATES on localhost](https://localhost:8443). The launcher uses a self-signed certificate for loopback development. To verify local requests with normal certificate validation, trust the generated `.ates/tls/local-cert.pem` for this profile. On an institutional deployment, use a TLS 1.2+ endpoint with a trusted certificate and the institution's hostname.

## Environment variables

Use [`.env.example`](.env.example) as a list of supported settings. ATES reads the process environment. Set variables in the terminal or deployment secret store before starting the corresponding command. Leave unused variables unset to use the defaults.

The launcher defaults to `.ates/ates.sqlite3`. Set `ATES_JWT_SECRET` to a random secret of at least 32 UTF-8 bytes to keep active sessions valid across restarts. An unset secret makes the local launcher create a fresh signing key at startup. Bootstrap reads the first password from the terminal or from the temporary `ATES_BOOTSTRAP_PASSWORD` variable in unattended setups.

Weekly grids start on Monday by default. Set `ATES_FIRST_WEEKDAY` to 1–7 (Monday–Sunday) for subsequently generated versions. Set `ATES_INSTITUTION` for the PDF heading and `ATES_BACKUP_DIRECTORY` for automatic local backups. See [operations](docs/OPERATIONS.md).

## Create a timetable

1. Sign in as Administrator. Open **User accounts**, add a Coordinator, then sign out.
2. Sign in as the Coordinator. In **Master data**, add and activate a term. Set the teaching days, start time, number of slots, and any blocked breaks in **Weekly grid**.
3. Add a department, courses, instructors, batches and rooms. Add offerings that join those records for the term. The **Import CSV** wizard provides templates and a validation preview for larger datasets.
4. Open **Dashboard → Generate timetable**. Leave the active term and Default configuration selected. Select **Generate**, then **View timetable**. A Draft with readiness problems shows a conflict report with the affected records.

For an exam schedule, add dated sessions in **Settings → Exam sessions**. An offering with an explicit roster needs all enrolled students listed. For an offering with no roster, the exam scheduler uses its whole batch. Open **Exams → Generate exam schedule**.

The six CSV templates use UTF-8 and can be downloaded from **Import CSV**. Match existing reference values exactly. Add dependencies first in the order shown above. Course, instructor, batch and room CSV files are independent once the department exists. Offerings depend on those records and a term. Enrollments depend on a saved offering and a Student account.

## PostgreSQL rehearsal

The local installer and tests accept only loopback PostgreSQL databases named `ates_disposable_*` or SQLite files under `.ates`. Create a fresh disposable PostgreSQL 15+ database with UTF-8. Set `ATES_MIGRATION_DATABASE_URL` to its owner connection using SQLAlchemy's `postgresql+psycopg` URL format. Set `ATES_DATABASE_URL` to the application's runtime connection. When using a separate worker login, set `ATES_WORKER_DATABASE_URL` to its connection for the same database. Keep credentials in the environment.

Use distinct, non-owner PostgreSQL logins with no superuser or RLS bypass. Run the following commands after creating those logins:

```text
python -m backend.cli migrate
python -m backend.cli grant-local-runtime --profile api --role ates_api
python -m backend.cli grant-local-runtime --profile worker --role ates_worker
python -m backend.cli bootstrap --email admin@example.test
python -m backend.cli serve
```

The migrations reproduce the 21-table catalog at revision `0001`. Subsequent local migrations add sessions, run snapshots and locks, import previews and exam support. Hosted reconciliation and deployment are tracked separately in the [phase ledger](docs/IMPLEMENTATION_PLAN.md). The recorded hosted definitions come from the read-only [catalog](docs/SUPABASE_CATALOG.json).

## Supabase configuration

ATES uses Supabase as a PostgreSQL host through its server-side SQLAlchemy connections. The React build calls FastAPI, and ATES manages application accounts and sessions. Obtain PostgreSQL connection details from the authorized Supabase project's **Connect** panel. Keep database credentials in server-side environment configuration and provision dedicated database logins for the API and worker. Use an encrypted connection. [Supabase PostgreSQL connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)

The existing hosted project has a recorded baseline. Use SQLite or the disposable PostgreSQL rehearsal above for development, tests and migration verification. Hosted deployment requires an authorized operator to reconcile the live schema, grants and RLS before configuring `ATES_DATABASE_URL` and, when using a distinct login, `ATES_WORKER_DATABASE_URL`. The local `bootstrap`, `migrate` and grant commands are for disposable targets. [Phase ledger](docs/IMPLEMENTATION_PLAN.md) · [Operations guide](docs/OPERATIONS.md)

## Verification

Build the frontend before starting the browser tests. On Windows, the browser tests default to installed Microsoft Edge. On Linux, install Playwright Chromium using `python -m playwright install chromium`. Set `ATES_BROWSER_CHANNEL=chrome` or `msedge` to use an installed branded Chromium browser.

```text
python -m pip install -r requirements-test.txt
python -m pytest -q -s
```

The SQLite tests create fresh synthetic databases. To run the PostgreSQL catalog rehearsal, set `ATES_TEST_DATABASE_URL` to a fresh, empty disposable database and run `python -m pytest -q tests/test_schema.py -k postgres`. Test output and screenshots from the actual local browser routes are under `.ates/evidence/`. The [requirement matrix](docs/TRACEABILITY.md) records which gates have evidence and which are still pending.

## Project structure

- `backend/` contains the FastAPI application, data layer, scheduling services, solver engines and worker.
- `frontend/` contains the React interface, Vite build configuration and npm lockfile.
- `migrations/` contains versioned Alembic migrations and the SQLite and PostgreSQL baselines.
- `tests/` contains API, solver, schema, recovery and browser tests using disposable synthetic data. `examples/` contains the reference benchmark.
- `docs/` contains architecture, operations, traceability and local verification. `output/pdf/` contains the reviewed user guides.

## Development workflow

Create a feature branch, follow [the repository instructions](AGENTS.md), and work against a disposable local database. Rebuild the browser interface after frontend changes and run the relevant tests before opening a pull request. When behavior or release evidence changes, update the [requirement matrix](docs/TRACEABILITY.md) and [phase ledger](docs/IMPLEMENTATION_PLAN.md). Contributors who need the original SRS should obtain an authorized copy from the project owner. The local source document contains student identifiers.

[Local verification and release checks](docs/LOCAL_VERIFICATION.md) · [CSV field guide](docs/CSV_FIELDS.md) · [Quick start PDF](output/pdf/ATES-Quick-Start.pdf) · [Role manual PDF](output/pdf/ATES-Role-Manual.pdf) · [Installation and administration PDF](output/pdf/ATES-Installation-and-Administration.pdf)

