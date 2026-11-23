# ATES V2 architecture

[Requirements matrix](TRACEABILITY.md) · [Implementation phases](IMPLEMENTATION_PLAN.md) · [Codex instructions](../AGENTS.md)

## The first useful timetable

A coordinator with an active term and complete data opens **Dashboard → Generate timetable → Generate → View timetable**. The Generate screen selects the active term, Timetable and its default configuration. The coordinator can change these choices. A weekly grid is the first success screen. The term, version and publication status stay visible so a draft result cannot be mistaken for the timetable students see.

| Moment | What the coordinator sees and can do |
| --- | --- |
| First visit to an empty installation | The dashboard shows the missing setup in dependency order. Create a term and generate its weekly grid once. Add or import the required data. Follow links directly to the missing entity and return to Generate with the term selected. |
| Ready to run | A short readiness summary shows offerings, unblocked slots and eligible rooms. Default settings work as supplied. Put seed, weights and rule parameters under Settings. The same defaults apply through the API. |
| Generating | One submission creates one version. Show phase and elapsed time, allow cancellation, poll every two seconds, and restore the run when the page reloads. Use an indeterminate indicator during search when completion percentage is unknown. |
| Success | Open the weekly grid for the generated version. Show class, teacher, room, time, lab blocks and breaks. Offer version selection, filters and the next permitted action. Exam results use a date-ordered list with room and seat counts. |
| Invalid input or no solution | Show each implicated offering, resource or rule, its reason and an action, such as adding a Lab room or unblocking a slot. Return to the same term after correction. Distinguish input defects, proved infeasibility, cancellation, time limit and internal interruption. |
| Approval and use | The Approver reviews counts, score and conflicts, then confirms publication. Faculty and Students reach their published timetable within two clicks after login. Exports use the exact view scope and filters. |

## Deployment and boundaries

One application repository, one React/Tailwind single-page interface, one FastAPI application, one separate Python solver worker and one relational database. FastAPI serves the built interface and API from the same origin. Use a small TLS endpoint at the front of the application. Keep the same application code on Windows and Linux. Select SQLite for a local demo and PostgreSQL for deployment through configuration. Node is a build tool. The solver runs outside the request process so other people can use the site while it works.

| Proposed location | Responsibility and contract |
| --- | --- |
| `frontend/` | React, Tailwind, English text resources, navigation, forms, accessible grids, download and status polling. Calls REST resources. Shows server validation next to the field and in a summary. |
| `backend/api/` | FastAPI routes, JWT session and role checks, request schemas, error and file responses, OpenAPI. Turn requests into application operations. |
| `backend/services/` | Use cases for setup, import, generation, editing, publishing, scoped viewing, export, audit and backup coordination. Own transaction boundaries. A shared query builds both the view and the export. |
| `backend/engine/` | Python domain inputs/results, CP-SAT timetable solver, NetworkX DSATUR exam solver, rule catalogue and independent validator. Each rule has model, validation and description operations. Discover rule implementations by code. Validator recomputes from assignments and source values, independent of solver decisions and constraint expressions. |
| `backend/data/` and `migrations/` | SQLAlchemy mappings, versioned migrations, indexes, repeatable reads of version inputs, atomic writes. Turn domain objects into the relational records in §5.1. No SQL in browser components. |
| `backend/worker/` | Poll and claim eligible Generating versions through the database. Pass an identifier across the process boundary. Load persisted inputs, solve, validate, and conditionally commit one terminal result. The API and worker share business data only through the database. |
| `tests/`, `examples/`, `docs/` | Unit/integration tests, real-browser journeys, synthetic import templates and repeatable fixtures, operator and user documentation. Add these as their phase makes them useful. |

Use a single local start command that runs migrations and starts TLS, API and worker. A development launcher may also build or serve the UI. Provide an explicit demo setup with synthetic records and a documented way to start empty. Keep routine coordinator tasks in the browser. A database-backed worker removes the need for a broker, cache or separate scheduling service. Pin the chosen open-source dependencies. The minimum platform and release checks are in the matrix.

### Existing Supabase database

The hosted data tier is the connected **ATES-DB** Supabase project. Inspection on 21 November 2026 found PostgreSQL 17.11 and all 21 expected public tables with all SRS foreign keys. Existing clash-prevention constraints, partial unique indexes, rule seed function and protection triggers provide the starting point for both database backends. [Schema comparison](TRACEABILITY.md#database-baseline-for-the-existing-supabase-project) · [Catalog evidence](SUPABASE_CATALOG.json)

FastAPI and the worker connect through SQLAlchemy using environment-supplied connection settings and a least-privilege backend account. React calls FastAPI. Keep database and service credentials on the server. Review any existing Supabase Data API exposure, grants and row-level policies so alternate access paths respect the same permissions. Inventory existing identity linkage and authentication settings before choosing an adapter. Verify §5.1.3.9 and FR-1.1–1.8 against the chosen login flow, including username, bcrypt cost, inactivity, lockout, role links and logout.

The Supabase migration list is empty. Establish a versioned baseline and exercise upgrade and restore on a disposable PostgreSQL copy. Keep SQLite behaviour aligned using local migrations and shared integration tests. The role model, migration history, composite-index gap and remaining application checks are recorded in the matrix. Preserve the hosted project throughout local implementation.

The local migration chain starts with the captured 21-table PostgreSQL schema and a corresponding SQLite revision. Subsequent revisions add the session table, the composite FK index, the run snapshot and claim record, logical teaching-session keys, CSV staging, exam exclusions, version-history guards and a timetable lab-block setting. Separate PostgreSQL owner, API and worker profiles were rehearsed against this chain. [Local verification](LOCAL_VERIFICATION.md)

## Access and interfaces

| Role | Browser destinations and allowed scope |
| --- | --- |
| Coordinator | Dashboard, all master data and imports, any availability, configurations and exam sessions, Generate, version history, both schedule views, conflicts, editing and exports. |
| Approver | Dashboard, read-only master data, version review, conflicts, both schedule views, publish/replace and exports. |
| Faculty | Dashboard, own availability, own published teaching timetable and exams associated with their offerings, filtered views and exports. |
| Student | Dashboard and own batch's published timetable, exams and exports, including on a phone. |
| Administrator | Dashboard, account and role management, filtered read-only audit. Table 7 and UR-22/23/25 allow read-only schedule viewing/export. Grant published read-only access, with no generation, adjustment or publication privileges. |

The server applies the same role, term, version and ownership checks to lists, details, counts, conflict reports, history and downloads. Restrict dashboard counts and labels to what the role may see. Use JWT in the Authorization header, server-tracked sliding inactivity and immediate revocation on logout/deactivation or role/password change. Background polling alone must not keep an idle user signed in. Apply the SRS password and lockout settings. Serve application data and interactive API documentation only to authorised users.

Keep the methods and paths in SRS Table 9. Use UTF-8 JSON over HTTPS, multipart UTF-8 CSV and typed binary downloads. Allow only the configured front-end origin. Extend the listed resources for cancel, preview/confirm, lock/unlock, undo, availability, account management and version duplication. `POST /schedules/generate` returns 202 with a version ID after preflight passes. `GET /schedules/{id}/status` survives refresh. Return an actionable defect list on invalid inputs, 403 on forbidden actions, 409 on a rejected move and 422 on a failed publish guard. The client sends the selected version/revision on edits so stale tabs cannot overwrite changes.

## Data and version integrity

Account for the 21 §5.1.3 business tables through a reproducible baseline and versioned migrations. Reuse existing Supabase objects that satisfy the requirements. Check actual column names, types, table-specific primary keys, defaults and every FK in both the column specifications and Table 30. Where an existing object uses a different name, record the mapping and test it on a disposable copy. Track departures from the specified physical schema as gaps until reconciled with a data-preserving migration. Additional operational fields need an identified requirement and an upgrade test.

| Group | Required tables |
| --- | --- |
| Organisation and teaching | `departments`, `academic_terms`, `time_slots`, `batches`, `courses`, `instructors`, `instructor_availability`, `rooms`, `course_offerings`, `enrollments` |
| Access and history | `users`, `import_logs`, `audit_logs` |
| Rules and versions | `scheduling_configs`, `constraint_rules`, `schedules`, `conflict_log` |
| Assignments | `timetable_entries`, `exam_slots`, `exam_entries`, `exam_room_allocations` |

- Generate weekly slots server-side from one set of grid settings. Use the unique key `(term_id, day_of_week, slot_index)`; preview a diff and apply it in one transaction. Saving the same grid twice changes nothing. Keep IDs, block reasons and availability for retained slots. If an edit would invalidate a referenced slot, keep the prior grid intact and explain the valid next action. Preserve earlier schedule inputs and display values.
- Derive contact minutes and whole-slot demand once per offering. Represent a logical lab block with a stable identifier across its per-slot database rows so the browser can move, lock and export the whole block. Resolve non-integral demand explicitly before generation.
- Allocate monotonically increasing version numbers per term and type with a unique constraint and transactional retry. A request token makes a repeated submission return the same version. Freeze inputs, including configuration, roster, locks and display metadata for each version. Prefer immutable referenced revisions with relational history where needed. Changes to courses, counts, settings or slot grids must leave old entries, exports, scores and validation reproducible.
- Persist the solver-created baseline for undo and the read revision for optimistic edits. The initial plan permits narrow supporting fields or normalised history relations when needed for snapshots, session tracking and run claims. Keep all 21 specified tables, constraints, 3NF and the named timetable-entry exception. Document additions and verify equivalents on both databases.
- Store events in UTC. Render dates DD/MM/YYYY and times on a 24-hour clock in Asia/Karachi. Weekly teaching slots and local exam dates/times are civil schedule values. Store text in UTF-8. Apply unique and check constraints, FK indexes, deactivation and append-only logs at the data boundary.
- Preflight checks independent defects together. After a valid request, the worker claims a version conditionally, solves without holding an open write transaction and commits assignments, allocations, score, stats, conflicts, audit and final state together. Cancellation/finalisation compete on the same guarded state transition. Failures preserve all prior schedules and leave no partial result. A server restart reconciles abandoned Generating runs to Infeasible with solver reason `interrupted`; fence late completions from the old process.

## Schedule lifecycle

| Event | Result |
| --- | --- |
| Create version or duplicate a retained version | New Draft with term and configuration. Regeneration from Generated or Infeasible keeps the source version and opens a new Draft. |
| Submit Draft | Run preflight. Input defects keep it Draft. Success makes it Generating. The ordinary Generate action combines draft creation and submission. |
| Complete generation | Independently validated feasible result becomes Generated. No result becomes Infeasible with a report and the actual solver outcome. On rejected solver output discard the assignments and log the defect. |
| Change Generated | Only the Coordinator may make an edit. Revalidate moves, update score, baseline flags and audit atomically. Reject an invalid move with its rule and retain the original entry. |
| Publish Generated | Only the Approver can publish. Validate again against the version inputs, check the revision and atomically archive any previous Published version of that term/type. Enforce uniqueness in the database. |
| Close term or replace publication | Published becomes Archived. Published and Archived entries are read-only. Privileged staff can view archived history. Returning to an earlier timetable means duplicating it and validating/approving a new version. |

## Scheduling contracts

**Timetable.** Represent each required lecture or lab block as a choice of start slot and room with explicit occupied slots. Enforce enabled H01–H10 on assignment and check them again independently. Maximise a documented weighted sum for S01–S06. Supply neutral/no-previous-version handling for S05. Return the best feasible candidate at the limit, elapsed time, score and actual solver status. Persist stable ordering, seed and deterministic search settings for reproducibility. Provide exact expected assignments on a forced-choice fixture and independently check invariants on larger fixtures.

The timetable score is the negative weighted sum of idle slots, repeat sessions on a day, excess batch sessions, excess consecutive teaching slots, changed placements where a previous version exists, and room fit rank. A score of zero has no penalty. A deterministic constructive assignment can supply CP-SAT with a feasible starting point. The independent validator checks any saved candidate, including the starting point when the search reaches its time limit before improving it. The engine reserves part of the configured budget for cleanup and reading the result.

**Exams.** Aggregate by course in the term, union student identities across offerings, and add an edge for each pair sharing a student. Where detailed enrollment is unavailable, apply A-4 consistently to conflict edges, daily counts and seat demand. Colour with DSATUR, map to dated sessions under daily limits and locks, allocate seats across rooms, and score ES01–ES03. If colouring uses too many sessions, try exact CP-SAT within the remaining budget. A poor greedy date or room choice also warrants an alternative assignment before reporting failure. Check enrolment overlap, student-day counts, room exclusivity, seat totals, capacities and completeness independently. Report affected courses, session/seat shortage where known and actual solver status. A heuristic colour count alone cannot prove a minimum shortfall.

An exam may use any active room with seats recorded in its snapshot. Coordinators can exclude an offered course for the selected term in Settings. Exam support stores distinct candidate identities in server-side snapshots. Reader views expose only the course and allocation data allowed by their role, with no roster identifiers.

## Source interpretations for implementation

These decisions fill gaps between SRS tables, figures and prose. Keep their rationale with the relevant tests. The PDF is the authority for any later clarification.

| Source | Working interpretation and acceptance boundary |
| --- | --- |
| FR-7.2 and Figures 8/13 | The figures omit the exact fallback. Implement and exercise the explicitly required CP-SAT attempt before a heuristic session shortfall becomes final. |
| FR-5.2/5.3, FR-7.3/7.4, Appendix A.5, §5.1.5 | The seven permanently enabled codes are H01, H02, H03, H08, E01, E04, E05. Other hard switches support confirmation and audit. E02 is conditional on being enabled. E03 is configurable in the catalogue, but exact seats and room capacity are also unconditional data-integrity rules. Disabling its model rule cannot authorise an invalid allocation. Keep C-6's whole-slot consecutive lab structure even when H09's optional model check is disabled. Show these structural guarantees in Settings. |
| FR-6.6, Table 26, §4.3.2 | No seventh schedule state is specified for cancellation. For an already-running version use Infeasible with solver status interrupted and an explicit user-cancelled reason. Display “Cancelled by coordinator” prominently. Keep a timeout without a candidate as Infeasible/unknown and identify the timeout. Neither is proof that a feasible assignment is impossible. |
| FR-2.9, H08/H09, Figure 4 | For the first release, split lecture minutes into whole slots and treat weekly lab minutes as one same-day contiguous block per offering by default. The SRS supplies no general lab-block size. Support a configured whole-slot block size when multiple blocks are needed. Preflight identifies unrepresentable remainders and asks for a slot/contact-hour or block-size correction. |
| A-4, FR-7.1/7.4, §5.1.3 | Use the explicit roster for an offering when complete. With no roster, use its whole batch, including stable synthetic identities for unlisted members if necessary. A partial roster cannot silently reduce seat demand. Flag unresolved counts for correction before solving. Default each offered course to examinable unless a stored term-level choice excludes it. |
| UR-24/27, FR-9.4/9.5, Tables 7 and 25 | Current published scope controls Faculty and Student access, including direct archive URLs. Staff with schedule-history permission view prior publications. Administrator schedule access follows Table 7's “All” read-only screens and the all-user viewing/export requirements. |
| FR-2.6, §5.1.5, Table 26 | An empty installation has no active term. Once set up, keep one Active term, switch atomically, and require a successor when closing the active term with other terms available. Close archives its published versions. |
| FR-11.2, §5.1.3 | One CSV row represents a logical session or exam. Combine all rooms for a multi-room exam in one quoted room field and list associated batches/instructors deterministically. Show exam date in the day field with Exam as type. |
| FR-8.5/8.7, DB-1/2 and §5.1.3 | The exam entry specification omits its manual-override flag, and the schema lists no baseline for undo. Add the minimal migration-backed support to preserve both behaviours and original version values. |
