# ATES V2 implementation plan

[Architecture](ARCHITECTURE.md) · [Requirement matrix](TRACEABILITY.md) · [Standing instructions](../AGENTS.md)

**Current handoff as of 22 November 2026.** The application runs locally through term setup, timetable and exam generation, review, publishing and scoped reader access. The coordinator's first timetable journey passed in Edge over HTTPS against SQLite and a separate CP-SAT worker. Release qualification is in progress. See [local verification and release checks](LOCAL_VERIFICATION.md) for the exact results and open checks, and [README](../README.md) for startup.

## Phase ledger

Update this table in place. At a handoff, record the last passing check, remaining evidence and the next executable task. Individual requirement status and evidence belong in the matrix.

| Phase | Usable outcome | Depends on | Status | Evidence / next action |
| --- | --- | --- | --- | --- |
| 1 | Sign in, reach role dashboard, administer accounts | Planning | Local gate passed | Edge account and sign-in flows, clock-controlled access tests and disposable PostgreSQL 17.11 catalog/role rehearsal passed. Hosted permissions remain a deployment review. |
| 2 | Prepare an active term and its teaching data through the browser | 1 | Local browser evidence recorded | Coordinator created a two-day grid and two offerings. Repeated grid saves kept IDs and the break. Faculty updated own availability, and cross-instructor mutation returned 403. |
| 3 | Generate and inspect a real weekly timetable | 2 | Browser milestone passed | Edge opened and refreshed the solver-saved lecture and lab. Independent negative cases cover H01–H10. Release concurrency and performance checks remain open. |
| 4 | Import the department's dataset and tune settings | 3 | Local evidence recorded | Six CSV types, mixed preview and valid-row import, rule switches, dated sessions, and browser run with defaults passed. Fresh-participant timing remains open. |
| 5 | Generate an exam schedule with verified room allocations | 4 | Local evidence recorded | Edge showed and filtered a split exam allocation at 360 px. The known four-colour DSATUR case triggered CP-SAT and fit in three sessions. |
| 6 | Adjust, approve and publish a version for its audience | 3, 5 | Local evidence recorded | Edge move and approval, stale revisions, post-review corruption and competing replacements exercised. Complete exam-edit and cross-batch browser variants ahead of release. |
| 7 | Export schedules and conflicts, inspect audit, use help | 6 | Local browser evidence recorded | All five roles downloaded filtered PDF and CSV in Edge. Admin filtered the export trail. A4 layout and the three PDF guides were checked. Representative grouped exports and remaining exam download variants stay in release checks. |
| 8 | Demonstrate release conformance and recovery | 1–7 | In progress | SQLite and PostgreSQL restore rehearsals passed. Node 18 build, Ubuntu runtime, reference/doubled fixtures and 50-user SQLite measurements recorded. Continue from the open performance and release-browser gates. |

Each phase is a vertical slice. Migrations, services, browser UI, permissions and tests for that slice ship together. The phase numbers express build order. The P-1 through P-8 identifiers in the matrix refer to SRS performance requirements. Keep earlier gates passing as each slice expands.

## Phase 1 · Existing database, login and dashboard

1. Use the dated Supabase catalog and the per-table comparison in the matrix. Reproduce the existing schema on a disposable PostgreSQL database. Compare columns, keys, indexes, trigger behaviour and rule defaults with the captured definitions. Account for the extra composite FK/index gap, empty recorded migration history and runtime-role grants. Test role restrictions on that copy. Refresh hosted metadata only if evidence is missing or the project has changed.
2. Reuse compatible objects and any established migration chain. For missing objects or different identifiers, first evaluate SQLAlchemy mapping, then additive migrations or a rehearsed data-preserving backfill. Use an isolated database populated with synthetic data to rehearse. Start with the SRS schema locally if the hosted definitions are unavailable. Keep a ledger item for hosted reconciliation, continue local phases, and use one versioned migration path per database. Do not issue DDL, seed, reset, repair migration history or deploy against the existing project as part of local implementation.
3. Add the local HTTPS launcher, pinned dependencies, migration tooling, FastAPI, React/Tailwind shell, environment-only secrets, server-side session/role checks, user management and append-only audit writes. Migrate only the first slice's dependencies. Offer explicit local bootstrap for the first Administrator and optional synthetic demo accounts. Set up protected OpenAPI and role-specific dashboard states. Fill schedule status/count widgets when their real data exists.
4. Establish repeatable unit, API/DB and browser commands for Windows and Linux. Document exact launch and test commands as soon as they exist. Run a clean SQLite startup and a PostgreSQL migration smoke test on a disposable database.

**Gate.** From a fresh install, sign in through a real browser, see the correct dashboard, create a linked Faculty and Student account with the required underlying records, change/reset a password and log out. Check five role menus, a forbidden direct request, lockout and expiry using a controlled clock. Refresh the page and verify session behaviour. Verify one TLS-backed browser flow and that the existing hosted project received zero writes. Keep later feature links out of navigation until functional.

## Phase 2 · A term ready for scheduling

Implement master-data tabs, active-term switching, server-generated slot grid, blocked periods, departments as reference data, courses, instructors, rooms, batches, offerings, enrollment links, availability and demand derivation. Deliver search, sort, pagination, edits and deactivation, with role-appropriate read-only views. Add the default timetable configuration through the normal setup service. Display counts, actionable readiness and the next setup link on the dashboard.

**Gate.** As Coordinator, create a term with two teaching days, a break, two offerings, one instructor and suitable rooms through visible forms. Save the grid twice, reload, add an offering, toggle a block and retry a duplicate offering. Assert stable slot IDs, expected count and preserved availability/block reasons. Run this against an empty database and an existing grid. As Faculty, mark own unavailability and see the regeneration warning. Verify cross-instructor edits are refused. Check one validation error and its recovery at 360 px.

## Phase 3 · First complete timetable in the browser

Implement database-backed run dispatch, preflight, deterministic CP-SAT search, ten hard rules, six weighted preferences, independent validation, conflicts, atomic persistence and six-state-compatible version creation. A Coordinator can generate with default configuration immediately after Phase 2. Show progress and elapsed time, cancel, reload, a result summary, filterable weekly grid, lab blocks and an exportable conflict report. Save version baselines and stable entry identities now for later manual work. Distinguish original data and generated assignments.

**Gate.** Start on the dashboard, select Generate timetable, accept the defaults and open the resulting weekly grid. Observe the real solver and committed DB result through the ordinary API. Compare exact demand, assignments, score and zero hard conflicts before and after refresh. Repeat with the same seed, cancel another run, restart during search and retry a double-click. Remove a needed room and obtain an actionable Draft defect. Separately run a well-formed but impossible dataset and obtain an Infeasible report. Inject an invalid candidate to prove FR-6.7 rejects it. Supply one deliberately violating validator test per H01–H10 and score tests for S01–S06. Time and test ordinary requests while generation runs. This is the first working timetable milestone.

## Phase 4 · Import, configuration and the coordinator's fast path

Deliver six downloadable UTF-8 templates with sample rows and field descriptions. The browser wizard previews a complete file before any commit, explains individual errors and can cancel or import only valid rows. Persist import logs and audit events. Support named configs, cloning, safe deletion, hard switches, mandatory codes, weights, parameters, seed and time bounds. Add non-overlapping dated exam sessions. Create defaults without forcing a visit to Settings. Publish the first two-page quick-start draft, keeping it current as publishing becomes available.

**Gate.** A coordinator imports a clean synthetic dataset, resolves a mixed-file rejection, confirms only the valid rows and reaches a generated timetable without opening advanced settings. Test all six CSV types, UTF-8 names, rejected oversized file, duplicate preview/confirm requests, and a cancelled batch. Exercise all seven protected codes, one configurable hard-rule confirmation, weights 0/10 and invalid overlapping exams. Repeat on a 5,000-row file and measure ≤15 s. Conduct the timed <15-minute coordinator acceptance with a fresh participant at release; an automated timing in this phase is rehearsal evidence.

## Phase 5 · Exam scheduling

Build the course graph from rosters or A-4 batch fallback, DSATUR colouring, dated-session mapping, exact CP-SAT fallback, room splitting, seat checks and exam preferences. Reuse the version pipeline, independent validator, progress and conflict views. Show a date/time-ordered list with filters, rooms and seats. Store run statistics. Carry stable exam identity, room allocation and initial baseline into Phase 6.

**Gate.** Allocate one shared-student elective and a repeated course without simultaneous exams, enforce the daily limit, and seat one large exam across rooms. Compare seat totals to distinct candidates. Run the known DSATUR fallback case and an unavoidable shortfall, plus insufficient rooms and fallback batch enrollment. Assert no partial allocations on failure. Verify all E01–E05 with individually bad candidates and all ES01–ES03 with preference comparisons. Reload and filter a real result at desktop and 360 px. Repeat on the reference fixture for the ≤30 s release measure.

## Phase 6 · Adjustment, publication and reader access

Add drag-and-drop and an equivalent labelled keyboard/touch move form. Move a whole lab or an exam allocation atomically, recompute its score, show conflicts immediately, mark overrides, lock/unlock, undo and regenerate with pins. Support version selection, duplicate to Draft, Approver summary, publish/replace confirmation, term closure, archive and restoring an older version by duplication. Complete published-only scoped views and dashboard routes for Faculty and Students.

**Gate.** Use separate Coordinator, Approver, Faculty and Student browser sessions. Make a valid move, reject an invalid move ≤1 s with its named rule, refresh and verify persistent state. Lock, regenerate, unlock and undo for classes and exams. Approve v1, then publish v2 while another session is viewing v1. Verify a single current publication per term/type, prior content in the staff archive and no hidden version or other-batch exposure. Exercise stale edits, simultaneous publish, a corrupt candidate and term closure. Readers find their own published timetable within two clicks after login.

## Phase 7 · Exports, audit and user documentation

Implement the shared scope/filter query for displayed data and exports. Produce A4 landscape PDFs, UTF-8 CSV and Coordinator bulk PDFs. Complete the Admin's audit filters and event coverage across all preceding phases. Deliver the screenshot-based role manual PDF, two-page quick-start guide from data entry to publication, installation/admin PDF, per-screen help, tooltips and interactive OpenAPI. Document schema, reusable interfaces, CSV templates, field expectations, privacy controls and third-party notices.

**Gate.** Download actual files through each authorised role. Open PDF and CSV, compare filtered record identities with the visible grid/list, inspect A4 layout and verify one page per batch/instructor for bulk export. Check a split exam and multi-slot lab each export one logical row. Deny unauthorized download requests. Filter audit by actor, time and action and match events to the performed changes. Test immutable audit and import logs. Walk the published quick start in a clean browser profile. Measure export limits from P-6.

## Phase 8 · Release qualification

- Rebuild from pinned dependencies with one startup command. Exercise clean installation and upgrade on SQLite and disposable PostgreSQL, on Windows and Linux. Check the imported Supabase schema mapping against dated evidence if available. Treat production application, hosted migration and publication outside the app as separate operator actions.
- Build an independently checked A-1 reference fixture at the stated ceilings, the up-to-80-course exam dataset, and a doubled workload (300 offerings, 120 rooms). Keep expected feasible/infeasible cases, seed, solver settings, machine profile and source revision with results.
- Run all P-1 to P-8 at the documented minimum 2 cores, 4 GB RAM and 10 GB free disk where applicable. Record raw request samples, dataset sizes, exact thresholds, typical and worst timings, p95, concurrency and worker-on/off comparisons. Label results from different hardware explicitly. Verify ≥70% unit coverage for engine and validator and ≥99% of valid runs without internal error in a documented representative run set.
- Exercise daily automatic backup and retention of seven copies, restoring to an isolated database and comparing schedules, master data, history and settings. Validate this for the selected deployment approach. Set up monthly availability measurement for 08:00–18:00 local working days and maintenance outside them. A short test cannot establish a month's 99% uptime.
- Test current Chrome, Firefox, Edge and Safari. Capture actual browser/version and device or viewport used. Browser-engine automation is useful evidence; record an actual Safari check separately. Rehearse on desktop at 1280 px and phone at 360 px, including keyboard navigation, touch move alternative, text labels, error focus, contrast and download. Ask a fresh Coordinator to run the <15-minute acceptance with only the two-page guide. Record result and assistance. Record actual click counts for Faculty and Student.
- Reconcile all 27 URs, 83 FRs, 17 use cases and all additional matrix gates with implementation/test evidence. Carry unperformed external gates as pending with the conditions needed to verify them. Confirm the original SRS fingerprint before sign-off.

**Gate.** Deliver a dated, reproducible acceptance report with pass/fail/pending results, recovery evidence, hosted-schema reconciliation status, browser matrix and links to each open issue. Claim full SRS conformance only when all relevant implementation, operational and human checks have evidence.

## Shared test data and evidence

| Fixture | What it proves |
| --- | --- |
| Empty installation and small forced-choice timetable | Setup requires no direct SQL. Use two or more days, a break, a lab block, known demand and an unavailable instructor. Constrain the solution enough to assert the exact grid. |
| Equally feasible timetable alternatives | Weighted preferences change the selected result. Holding data, config and seed fixed reproduces the result, including across regeneration with a pinned entry. |
| Invalid input versus impossible timetable | Missing eligible room yields a Draft readiness explanation. Two batches sharing an instructor with too few compatible slots can pass simple preflight and fail search with a reason. |
| Exam graph fixtures | Include explicit student overlap across batches, batch-only fallback, multi-room exam, daily limit, known heuristic/exact difference with fixed tie order and a proven session shortfall. Record graph edges and target colouring as fixture expectations. |
| Publication and privacy | Two terms, both schedule types, two versions, two batches, two faculty, an Approver and an Administrator expose scope errors, racing writes and snapshot regressions. |
| Reference and doubled load | Use deterministic synthetic data and independent checksums/counts. Record timings separately from functional pass/fail. |

**Concrete exact-fallback fixture (FR-7.2).** Create courses A through G in alphabetical insertion order and one distinct student enrolled in the two courses of each pair: AC, AD, AE, BD, BF, BG, CD, CF, DG, EF, EG. Supply complete rosters, adequate rooms and three dated sessions on separate days. With maximum saturation, then maximum degree, then alphabetical tie breaking and lowest available colour, DSATUR gives four groups: DF, AB, CE, G. An exact three-session assignment exists: DE / AFG / BC. Check that the actual DSATUR path triggers the fallback, that the final assignments have no shared-student clash and that no session-shortfall report is issued. Any valid three-session assignment passes.

For each phase, run relevant engine/API/DB cases and at least one real-browser scenario against the actual server and database. Record the command, test name, database, browser/viewport, expected and actual result, and artifact or log location. A failed or unavailable gate stays visible. Continue independent local work and resume with the first unfinished dependency.
