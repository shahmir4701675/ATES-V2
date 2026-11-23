# ATES V2 · repository instructions for Codex

## Mandate

Build the Auto Timetable / Exam Scheduler for the five SRS roles. The coordinator's shortest useful journey is to prepare a term, generate with defaults and open the resulting weekly timetable in a real browser. Simplify implementation and navigation while delivering every SRS requirement, including medium/low priorities, all scheduling rules, quality targets and user documentation.

A planning or review request authorises only that work. Begin the numbered phases when the user gives an implementation instruction such as “start” or “continue implementation.” That instruction covers the full plan. Advance through passing phases without seeking routine confirmations or requiring the user to compose a prompt for each phase. A later explicit request to pause or narrow the work takes precedence.

## Read at the start of each implementation session

1. Read the phase ledger and last evidence in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). Resume the earliest incomplete dependency. Inspect existing files and any user changes before editing.
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the browser flow, deployment, existing Supabase baseline, data model, version guards and documented source interpretations.
3. Open [docs/TRACEABILITY.md](docs/TRACEABILITY.md) for the relevant SRS IDs, test cases and current status. Use the authorized local copy of `SRS.pdf` for exact wording, tables and diagrams. The original contains student identifiers. Obtain it from the project owner if it is absent from your checkout. Page references in project notes are printed page numbers.
4. Verify the source fingerprint when starting work that depends on the SRS and before release. In PowerShell run `Get-FileHash -Algorithm SHA256 -LiteralPath .\SRS.pdf`. Expected SHA-256 is `6F6D9D36C98C772B5F8259FCEB8E136A3C141F2C6CB1F1F3A68692DBA905F500` (332,733 bytes, 62 PDF pages). Treat the PDF as read-only. If the fingerprint differs, preserve the file and investigate which baseline the owner intends.

## Existing Supabase project

A read-only inspection on 21 November 2026 confirmed that ATES-DB contains the 21 expected public tables and all 36 SRS scalar foreign keys. Use [the catalog](docs/SUPABASE_CATALOG.json) and [the schema comparison](docs/TRACEABILITY.md#database-baseline-for-the-existing-supabase-project) as the starting point. Preserve matching schema and data. Refresh missing or stale metadata through authorised read-only access. Begin Phase 1 on disposable PostgreSQL and SQLite, recording separate evidence for runtime behaviour and deployed conformance.

Local implementation may create local migrations and test databases. It does not grant permission to mutate the hosted project. Never run resets, seed commands, bulk deletes, DDL, migration-history changes or test suites against the existing Supabase database during implementation. Use local synthetic fixtures and guard test/seed targets. Preserve unrelated objects, existing data and user edits. Keep connection strings, passwords and service secrets in environment configuration.

## Engineering boundaries

- Use the SRS technology stack and the one-application architecture. React/Tailwind calls FastAPI over HTTPS. Use SQLAlchemy, versioned migrations and a separate DB-backed Python worker for solver runs. Keep OR-Tools CP-SAT, NetworkX DSATUR with the exact fallback and independent validation outside the web layer.
- Treat every schedule result, edit and publish as a guarded server operation. Protect prior versions, avoid duplicate submissions and repeated slot insertion, and write entries with their outcome atomically. Preserve locks on regeneration and enforce role/scope checks on exports as well as views.
- Keep the original IDs in tests and evidence. Add new rules through the shared rule contract, use configuration for institutional values and keep user-facing strings in resources. Keep the first release within SRS Table 1.
- Use documented working interpretations where the SRS leaves a gap. Log a new interpretation, its SRS references and regression test if needed. Preserve explicit requirements. Escalate only a genuine missing decision that changes scope or makes further dependent work unsafe.
- Build through the normal browser workflow. Use visible labels, field-level feedback plus an error summary, clear statuses and responsive views. Default the active term and configuration. Preserve entered data and selection when users fix errors. Avoid placeholder buttons and mock solver results on a production path.

## Phase completion and resumption

1. Implement the current user journey end to end. Include its schema changes, API, role checks, browser screens, failure recovery and specific regression tests.
2. Run its gate and relevant earlier regressions. Use a real browser against the running API, real solver and actual test DB where applicable. Verify refresh, allowed and forbidden paths, invalid input and a narrow viewport. API-only checks cannot sign off a browser journey.
3. Update the matrix with actual status, named test/command and evidence. Update the phase ledger with the last result, outstanding items and next task. Document actual setup and run commands when they exist.
4. Continue with the next dependency-ready phase. If a service, browser, human trial or month of operational data is unavailable, record exactly which result is pending and continue all independent local work. Report measured thresholds separately from expected ones.
5. Release requires the full matrix, both SQL engines, the four named browsers, reference-size and doubled-load checks, backup/restore, documentation and recorded usability results. Keep missing evidence visible; “planned”, “implemented” and “verified” are distinct.

## Current entry point

The local project is at the planning handoff. Start future implementation with Phase 1 in the ledger. The ledger is authoritative for progress once work begins.
