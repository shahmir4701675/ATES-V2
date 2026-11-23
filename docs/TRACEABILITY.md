# ATES V2 requirement traceability matrix

[Architecture and interpretations](ARCHITECTURE.md) · [Phase gates](IMPLEMENTATION_PLAN.md)

Obtain an authorized copy of the original `SRS.pdf` from the project owner when exact wording or figures are needed. The source contains student identifiers.

Page numbers below are the printed SRS pages. Add four for the PDF viewer's page number. Table 23 supplies the UR–FR mapping. Each FR row names its owning feature, applicable phase(s), source priority and an observable acceptance check. **All 83 FRs are in release scope**, including the four SRS “should” items. Section headings supply source locations for the additional gates. Local descriptions are test intentions and the original wording governs.

Status starts at **Planned**. Replace it with **In progress**, **Implemented** or **Verified**. Use **Blocked** with a reason when evidence needs an external resource. In the Evidence column record an actual test path and named case, test report, measurement or dated human observation. A phase assignment is a plan, never proof. A UR inherits verification only when all its linked FRs and the corresponding browser journey pass.

## User requirements and SRS reverse mapping

| SRS ID | User outcome | SRS actor | Implemented by (Table 23) |
| --- | --- | --- | --- |
| UR-01 | Sign in | All | FR-1.1, FR-1.2, FR-1.3, FR-1.4 |
| UR-02 | Administer user accounts | Administrator | FR-1.2, FR-1.6, FR-1.7 |
| UR-03 | Use permitted functions | All | FR-1.5, FR-1.8 |
| UR-04 | Maintain courses | Coordinator | FR-2.1, FR-2.2, FR-2.11, FR-2.12 |
| UR-05 | Maintain instructors | Coordinator | FR-2.3, FR-2.11, FR-2.12 |
| UR-06 | Maintain rooms | Coordinator | FR-2.4, FR-2.11, FR-2.12 |
| UR-07 | Maintain batches | Coordinator | FR-2.5, FR-2.11, FR-2.12 |
| UR-08 | Define terms and weekly grids | Coordinator | FR-2.6, FR-2.7 |
| UR-09 | Assign offerings | Coordinator | FR-2.8, FR-2.9, FR-2.11 |
| UR-10 | Mark availability | Faculty, Coordinator | FR-3.1, FR-3.2, FR-3.3, FR-3.4 |
| UR-11 | Record student enrollments | Coordinator | FR-2.10, FR-4.1 |
| UR-12 | Import CSV and see rejections | Coordinator | FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-4.5 |
| UR-13 | Configure constraints and solver | Coordinator | FR-5.1, FR-5.2, FR-5.3, FR-5.4, FR-5.5, FR-5.6, FR-5.8, FR-6.4, FR-7.6 |
| UR-14 | Define exam sessions and limits | Coordinator | FR-5.4, FR-5.7, FR-5.8, FR-7.3 |
| UR-15 | Generate weekly timetable | Coordinator | FR-2.9, FR-5.2, FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.5, FR-6.6, FR-6.7, FR-6.8, FR-6.9 |
| UR-16 | Generate exams and seats | Coordinator | FR-5.2, FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.5, FR-7.6, FR-7.7 |
| UR-17 | Understand generation failure | Coordinator | FR-6.1, FR-6.5, FR-7.5, FR-8.1, FR-8.2 |
| UR-18 | Retain and regenerate versions | Coordinator | FR-3.4, FR-6.2, FR-6.8, FR-6.9, FR-9.1, FR-9.5 |
| UR-19 | Move and validate entries | Coordinator | FR-8.1, FR-8.3, FR-8.4, FR-8.5, FR-8.7, FR-10.6 |
| UR-20 | Lock entries across runs | Coordinator | FR-6.10, FR-8.6, FR-10.6 |
| UR-21 | Review and publish | Approver | FR-9.1, FR-9.2, FR-9.3, FR-9.6 |
| UR-22 | Filter timetables | All | FR-10.1, FR-10.2, FR-10.3, FR-10.6, FR-10.7, FR-10.8 |
| UR-23 | Filter exams | All | FR-10.4, FR-10.8 |
| UR-24 | See own published schedule | Faculty, Student | FR-9.4, FR-10.5, FR-10.8, FR-11.4 |
| UR-25 | Export current view | All | FR-11.1, FR-11.2, FR-11.3, FR-11.4, FR-11.5 |
| UR-26 | Inspect audit trail | Administrator | FR-4.5, FR-11.5, FR-12.1, FR-12.2, FR-12.3 |
| UR-27 | View historical publications | All | FR-9.3, FR-9.5 |

## User journeys · §3.3.1, Table 25

Run each use case through the normal UI with the actors and authorisation rules in the architecture. The generated schedule, conflict list and role tests in the plan specify the expected outcomes. UC-10 is exercised inside both generation journeys.

| Use case | Journey | SRS user requirements | Phase | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| UC-01 | Log in | UR-01, UR-03 | 1 | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| UC-02 | Manage accounts | UR-02 | 1 | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| UC-03 | View audit | UR-26 | 7 | Verified | [Edge audit case](../tests/test_exports.py) filtered Faculty export events by actor and action. |
| UC-04 | Manage master data | UR-04, UR-05, UR-06, UR-07, UR-08, UR-09, UR-11 | 2 | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| UC-05 | Import CSV | UR-12 | 4 | Verified | [Import template, preview and browser cases](../tests/test_imports_settings.py). P-5 rehearsal covered 5,000 rows. |
| UC-06 | Configure rules | UR-13 | 4 | Implemented | [Configuration routes](../backend/api/settings.py) and [settings tests](../tests/test_imports_settings.py). Add full interactive settings gate. |
| UC-07 | Define exam sessions | UR-14 | 4 | Implemented | [Configuration routes](../backend/api/settings.py) and [settings tests](../tests/test_imports_settings.py). Add full interactive settings gate. |
| UC-08 | Generate timetable | UR-15, UR-18 | 3 | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| UC-09 | Generate exams | UR-16 | 5 | Verified | [Four-colour fallback and split exam Edge journey](../tests/test_exams.py). |
| UC-10 | Validate input | UR-17 | 3, 5 | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| UC-11 | Read conflicts | UR-17 | 3, 5 | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| UC-12 | Adjust and lock | UR-19, UR-20 | 6 | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| UC-13 | Approve and publish | UR-21, UR-27 | 6 | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |
| UC-14 | View timetable | UR-22, UR-24 | 3, 6 | Verified | [Weekly timetable](../tests/test_timetable.py) and [date-ordered exams](../tests/test_exams.py) opened and filtered in Edge at 360 px with real saved results. |
| UC-15 | View exams | UR-23, UR-24 | 5, 6 | Verified | [Weekly timetable](../tests/test_timetable.py) and [date-ordered exams](../tests/test_exams.py) opened and filtered in Edge at 360 px with real saved results. |
| UC-16 | Export schedule | UR-25 | 7 | Verified | [Edge download case](../tests/test_exports.py) downloaded the filtered CSV and PDF as all five roles. |
| UC-17 | Set availability | UR-10 | 2 | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |

## FA-1 · Authentication and access · printed pp. 19–20

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-1.1 | UR-01 | H / shall | Sign in and expire an inactive session | 1 | An active account receives a JWT. Advance the idle clock by 30 minutes and show that the next protected request requires login. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.2 | UR-01, UR-02 | H / shall | Protect passwords | 1 | Reject seven characters, accept eight, inspect stored bcrypt cost ≥12 and distinct salts for equal test passwords. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.3 | UR-01 | M / shall | Lock after consecutive failures | 1 | Four failures allow a correct login. Five lock for 15 minutes, show remaining time, record event and allow login when elapsed. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.4 | UR-01 | M / shall | End session and change own password | 1 | Log out and retry the same token. Change own password and sign in with the new credential. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.5 | UR-03 | H / shall | Authorise every API request | 1 | Exercise permitted and forbidden routes for all five roles. A forbidden authenticated request returns 403. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.6 | UR-02 | H / shall | Administer accounts | 1 | Create, edit, deactivate, reactivate, reset and assign one of five roles. Verify instructor and batch links and immediate access changes. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.7 | UR-02 | M / shall | Retain accounts with history | 1 | Attempt to remove a user with recorded actions. Deactivate them and confirm their historical actions remain attributable. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |
| FR-1.8 | UR-03 | M / shall | Role-specific navigation | 1 | Sign in as each role. Check permitted menus, buttons and direct URL behaviour against the role table. | Verified | SQLite clock and access cases in [test_access.py](../tests/test_access.py) and HTTPS Edge [account journey](../tests/test_browser.py). |

## FA-2 · Master data · printed pp. 20–21

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-2.1 | UR-04 | H / shall | Maintain courses | 2 | Create, read, edit and deactivate a course, require unique code, title, credits, lecture/lab hours and department. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.2 | UR-04 | M / shall | Check course hours | 2 | Exercise zero total contact hours and each negative credit/hour case. Reject in form, API and database. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.3 | UR-05 | H / shall | Maintain instructors | 2 | Save name, department, daily/weekly maxima and unique email. Reject invalid limits and duplicates, then deactivate. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.4 | UR-06 | H / shall | Maintain rooms | 2 | Create/edit/deactivate rooms with code, building, positive capacity and Lecture, Lab or Exam Hall type. Reject duplicate code. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.5 | UR-07 | H / shall | Maintain batches | 2 | Save programme, year, section and positive strength. Reject duplicate combination and zero strength, then deactivate. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.6 | UR-08 | H / shall | Maintain terms | 2 | Create named dated terms. Switch active term in one transaction and verify concurrent attempts cannot create two active terms. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| FR-2.7 | UR-08 | H / shall | Generate and block weekly slots | 2 | Generate days × slots from first time, length (default 60 min) and count. Block with a reason. Save twice and refresh with stable count and IDs. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| FR-2.8 | UR-09 | H / shall | Assign course offerings | 2 | Save term/course/batch/instructor/count. Reject a second offering of the same course, batch and term. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| FR-2.9 | UR-09, UR-15 | H / shall | Derive weekly demand | 2 | For 60- and 30-minute terms compare derived lecture slots and lab blocks to contact minutes. Report an unrepresentable duration. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| FR-2.10 | UR-11 | M / shall | Maintain enrollments | 2 | Add, list and remove a Student–offering link. Reject a duplicate and a non-Student account. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.11 | UR-04, UR-05, UR-06, UR-07, UR-09 | H / shall | Protect referenced master data | 2, 6 | Try to delete referenced data, offer deactivation and verify the stored version can still be opened. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-2.12 | UR-04, UR-05, UR-06, UR-07 | L / shall | Search, sort and page lists | 2 | Exercise all master tabs with >25 records. Default first page has 25, sorting and search remain stable across pages. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |

## FA-3 · Availability · printed pp. 21

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-3.1 | UR-10 | M / shall | Faculty availability | 2 | Toggle cells in the logged-in teacher's weekly grid. Reload for persistence and reject changing a different teacher. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| FR-3.2 | UR-10 | M / shall | Coordinator availability | 2 | Change two instructors independently and verify persisted results. | Implemented | Master-data and availability routes. [SQLite and Edge setup evidence](../tests/test_master.py). Full named acceptance variants remain open. |
| FR-3.3 | UR-10 | M / shall | Default availability | 2, 3 | With no availability record every eligible slot is available. An explicit unavailable mark removes that slot when H06 is enabled. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |
| FR-3.4 | UR-10, UR-18 | L / shall | Explain effect of edits | 2, 3 | Change availability while viewing an existing version. Show regeneration guidance and verify previous entries do not change. | Verified | [Term and availability cases](../tests/test_master.py) on SQLite and Edge. Repeat save, duplicate offering recovery, break retention and private availability exercised. |

## FA-4 · Imports · printed pp. 21–22

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-4.1 | UR-11, UR-12 | H / shall | CSV types, size and templates | 4 | Download all six templates. Upload valid UTF-8 for courses, instructors, rooms, batches, offerings and enrollments. Reject non-CSV and files above 10 MB. | Verified | [Import template, preview and browser cases](../tests/test_imports_settings.py). P-5 rehearsal covered 5,000 rows. |
| FR-4.2 | UR-12 | H / shall | Validate before storing | 4 | Preview a file with missing, malformed, out-of-range, duplicate and unknown reference values. Confirm zero business rows written until confirmation. | Verified | [Import template, preview and browser cases](../tests/test_imports_settings.py). P-5 rehearsal covered 5,000 rows. |
| FR-4.3 | UR-12 | H / shall | Report individual row errors | 4 | Upload multiple bad rows and verify each rejected line number, column and plain-language reason. | Verified | [Import template, preview and browser cases](../tests/test_imports_settings.py). P-5 rehearsal covered 5,000 rows. |
| FR-4.4 | UR-12 | M / shall | Confirm valid rows or cancel | 4 | Use both choices on a mixed file. Confirm writes only accepted rows once, cancel writes none, recheck concurrent changes. | Verified | [Import template, preview and browser cases](../tests/test_imports_settings.py). P-5 rehearsal covered 5,000 rows. |
| FR-4.5 | UR-12, UR-26 | M / shall | Record import history | 4 | Match filename, actor, time and total/imported/rejected counts to committed rows and the audit event. | Verified | [Import template, preview and browser cases](../tests/test_imports_settings.py). P-5 rehearsal covered 5,000 rows. |

## FA-5 · Configuration · printed pp. 22

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-5.1 | UR-13 | H / shall | Seed the complete rule catalogue | 3–5 | For each schedule type compare default rule codes, type, enable flag, weight and parameter to Appendix A.5 and the rule matrix below. | Verified | [Configuration cases](../tests/test_imports_settings.py) cover all seven protected rules, acknowledgement, 0/10 weights and overlapping exam sessions. |
| FR-5.2 | UR-13, UR-15, UR-16 | H / shall | Keep mandatory rules enabled | 4 | Try disabling each of the seven protected codes through UI and API. Each stays enabled. | Verified | [Configuration cases](../tests/test_imports_settings.py) cover all seven protected rules, acknowledgement, 0/10 weights and overlapping exam sessions. |
| FR-5.3 | UR-13 | M / shall | Confirm other hard-rule changes | 4 | Disable a configurable hard rule, first cancel then confirm. Verify the warning, resulting configuration and audit event. | Verified | [Configuration cases](../tests/test_imports_settings.py) cover all seven protected rules, acknowledgement, 0/10 weights and overlapping exam sessions. |
| FR-5.4 | UR-13, UR-14 | H / shall | Set weights and parameters | 4 | Set soft weights 0 and 10, reject values outside that range, and persist applicable integer limits, including daily exams. | Verified | [Configuration cases](../tests/test_imports_settings.py) cover all seven protected rules, acknowledgement, 0/10 weights and overlapping exam sessions. |
| FR-5.5 | UR-13 | M / shall | Set solver budget and seed | 4 | Verify 120 s default, allow 10 and 600, reject 9 and 601, round-trip seed. | Implemented | [Configuration routes](../backend/api/settings.py) and [settings tests](../tests/test_imports_settings.py). Add full interactive settings gate. |
| FR-5.6 | UR-13 | M / shall | Manage named configurations | 4 | Create two configs per term/type, clone and edit independently. Delete an unused config and protect a referenced one. | Implemented | [Configuration routes](../backend/api/settings.py) and [settings tests](../tests/test_imports_settings.py). Add full interactive settings gate. |
| FR-5.7 | UR-14 | H / shall | Define exam sessions | 4 | Persist date, start/end and label. Reject same-day overlap, allow adjacent windows and matching times on different dates. | Verified | [Configuration cases](../tests/test_imports_settings.py) cover all seven protected rules, acknowledgement, 0/10 weights and overlapping exam sessions. |
| FR-5.8 | UR-13, UR-14 | M / shall | Preflight configuration | 3–5 | Reject invalid weights or budget and an exam run with zero sessions before solving. Show where to fix each. | Implemented | [Configuration routes](../backend/api/settings.py) and [settings tests](../tests/test_imports_settings.py). Add full interactive settings gate. |

## FA-6 · Timetable generation · printed pp. 23

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-6.1 | UR-15, UR-17 | H / shall | Check all input defects | 3 | Remove an instructor, eligible room and necessary unblocked slots from fixtures. Report all defects before solving and keep Draft. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.2 | UR-15, UR-18 | H / shall | Start a new version | 3 | Submit the chosen term/configuration as Coordinator, receive 202 and new Generating version. Retry the same submission without a second version. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.3 | UR-15 | H / shall | Model timetable assignment | 3 | Solve each offering's demand as slot/room choices and independently check all enabled H01–H10, including every occupied lab slot. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.4 | UR-13, UR-15 | H / shall | Optimise preferences | 3 | On tiny enumerable schedules compute the expected best weighted score, then change a weight to demonstrate its effect. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.5 | UR-15, UR-17 | H / shall | Respect time limit | 3 | Control solver outcomes to return best feasible at the deadline or Infeasible with actual reason when none was found. Also time a real run. | Implemented | Worker, timeout, queued cancellation and stale-lease cases in [test_timetable.py](../tests/test_timetable.py). Live in-search cancellation and injected persistence failure remain ahead of release. |
| FR-6.6 | UR-15 | M / shall | Show progress and cancel | 3 | Observe phase and elapsed time, refresh mid-run and cancel. Verify prior versions and their entries are byte-for-byte equivalent in a canonical export. | Implemented | Worker, timeout, queued cancellation and stale-lease cases in [test_timetable.py](../tests/test_timetable.py). Live in-search cancellation and injected persistence failure remain ahead of release. |
| FR-6.7 | UR-15 | H / shall | Validate before committing | 3 | Inject a bad candidate at the solver boundary. Independently identify its rule and verify zero generated assignments and no Generated state. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.8 | UR-15, UR-18 | H / shall | Store a complete result | 3 | Reload and verify entries, objective score, actual solver status, run time and Generated state together. Simulate a failed transaction. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.9 | UR-15, UR-18 | L / should | Repeat a run | 3 | Use identical frozen input, config, seed and pinned environment. Compare canonical assignments and score across two fresh runs. | Verified | [Forced-choice engine, worker and Edge cases](../tests/test_timetable.py) covered saved score and entries, idempotency and independent rejection of a corrupt candidate. |
| FR-6.10 | UR-20 | M / shall | Preserve locked sessions | 6 | Pin a logical session, regenerate and compare room and all occupied slots. Contradict the pin and require an explanatory failure. | Implemented | A moved and locked lecture retained its exact room and slot on regeneration. [Timetable pin regression](../tests/test_versions.py). Full lab and exam lock variants remain open. |

## FA-7 · Exam generation · printed pp. 23–24

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-7.1 | UR-16 | H / shall | Build course conflict graph | 5 | Across multiple batches, elective/repeat enrollment and fallback cohorts, compare expected course nodes and exact shared-student edges. | Implemented | [Exam graph and validator cases](../tests/test_exams.py) and [reference fixture](../examples/reference_benchmark.py). Repeat explicit enrolled-roster and advanced preference cases against persisted results. |
| FR-7.2 | UR-16 | H / shall | Colour and apply exact fallback | 5 | Use a known colourable fixture where DSATUR needs excess colours. Verify CP-SAT finds a valid assignment. Test a genuinely impossible clique too. | Verified | [Four-colour fallback and split exam Edge journey](../tests/test_exams.py). |
| FR-7.3 | UR-14, UR-16 | H / shall | Enforce daily exam limit | 5 | Build a student with multiple non-overlapping sessions on one date. Check the configured maximum for every student/day. | Implemented | [Exam graph and validator cases](../tests/test_exams.py) and [reference fixture](../examples/reference_benchmark.py). Repeat explicit enrolled-roster and advanced preference cases against persisted results. |
| FR-7.4 | UR-16 | H / shall | Allocate exam rooms and exact seats | 5 | Split an exam across rooms. Compare distinct enrollee count with seat totals and check each room's capacity and exclusivity per session. | Verified | [Four-colour fallback and split exam Edge journey](../tests/test_exams.py). |
| FR-7.5 | UR-16, UR-17 | H / shall | Explain session shortfall | 5 | Use a clique needing three sessions with two defined. Verify Infeasible, one-session shortfall, affected courses and no partial assignments. | Implemented | [Exam graph and validator cases](../tests/test_exams.py) and [reference fixture](../examples/reference_benchmark.py). Repeat explicit enrolled-roster and advanced preference cases against persisted results. |
| FR-7.6 | UR-13, UR-16 | M / shall | Optimise exam preferences | 5 | Compare valid allocations by date spread, room count and same-building preference. Exercise individual weights and the combined score. | Implemented | [Exam graph and validator cases](../tests/test_exams.py) and [reference fixture](../examples/reference_benchmark.py). Repeat explicit enrolled-roster and advanced preference cases against persisted results. |
| FR-7.7 | UR-16 | H / shall | Store exam results | 5 | Reload exam entries, room allocations and counts of courses, sessions and rooms used. Generated requires a complete validated result. | Implemented | [Exam graph and validator cases](../tests/test_exams.py) and [reference fixture](../examples/reference_benchmark.py). Repeat explicit enrolled-roster and advanced preference cases against persisted results. |

## FA-8 · Conflicts and adjustments · printed pp. 24

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-8.1 | UR-17, UR-19 | H / shall | Produce a complete conflict list | 3, 5 | Independently validate both schedule types. Report each enabled hard violation with type, severity, entities and description. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| FR-8.2 | UR-17 | M / shall | Filter and export conflicts | 3, 5 | Coordinator and Approver filter a report by type and download its CSV. Verify the selected conflicts and deny other roles. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| FR-8.3 | UR-19 | H / shall | Move timetable sessions and exams | 6 | As Coordinator move a Generated class block or exam to a new time and room(s). Reject edits to other states. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| FR-8.4 | UR-19 | H / shall | Refuse invalid moves quickly | 6 | Introduce a known clash. In ≤1 s report the violated rule, undo the visual move, and verify unchanged stored entries. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| FR-8.5 | UR-19 | M / shall | Mark manual overrides | 6 | After an accepted edit, reload the entry of either schedule type and check its persisted override indicator. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| FR-8.6 | UR-20 | M / shall | Lock and unlock | 6 | Toggle a whole block or exam. Regenerate with the pin, then unlock and verify it can move. Check both UI and stored state. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| FR-8.7 | UR-19 | L / should | Undo all manual edits | 6 | Make several edits, undo the version's manual changes, refresh, and compare entries, flags and score with the saved generated baseline. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |

## FA-9 · Versioning and publication · printed pp. 25

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-9.1 | UR-18, UR-21 | H / shall | Guard the six-state lifecycle | 3, 5, 6 | Exercise all Table 26 edges including term close and new Draft derivation. Reject other transitions and direct state writes. | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |
| FR-9.2 | UR-21 | H / shall | Guard publication | 6 | Only an Approver can publish a Generated version. A fresh independent violation refuses publication even with a stale clean summary. | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |
| FR-9.3 | UR-21, UR-27 | H / shall | Archive superseded publication | 6 | Concurrently publish distinct versions. Assert at most one Published per term/type, old publication Archived, other term/type untouched. | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |
| FR-9.4 | UR-24 | H / shall | Restrict unpublished schedules | 6 | Faculty and Student see only authorised Published content in dashboards, details, lists, history and downloads. | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |
| FR-9.5 | UR-18, UR-27 | M / shall | Retain and duplicate versions | 3, 6 | Generate sequential version numbers, duplicate to a new Draft, reopen archived history with staff access and verify earlier values after data edits. | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |
| FR-9.6 | UR-21 | M / shall | Review before publication | 6 | Show session/exam count, soft score and conflict count for the selected revision before the Approver confirms. | Implemented | [Publish, replace, archive and reader cases](../tests/test_versions.py) passed locally. Simultaneous publication and complete cross-batch browser cases remain open. |

## FA-10 · Schedule views · printed pp. 25–26

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-10.1 | UR-22 | H / shall | Display weekly grid | 3 | See weekly days/slots and correct placement for a selected batch, instructor, room or course, including multi-slot labs and blocked cells. | Verified | [Weekly timetable](../tests/test_timetable.py) and [date-ordered exams](../tests/test_exams.py) opened and filtered in Edge at 360 px with real saved results. |
| FR-10.2 | UR-22 | H / shall | Display session details | 3 | Open a grid cell and verify course code/title, session type, instructor, room, day and time. | Verified | [Weekly timetable](../tests/test_timetable.py) and [date-ordered exams](../tests/test_exams.py) opened and filtered in Edge at 360 px with real saved results. |
| FR-10.3 | UR-22 | H / shall | Filter timetables | 3, 6 | Change term, permitted version, batch, instructor, room, course and day. Compare results to expected scoped assignments. | Implemented | [Version browser cases](../tests/test_versions.py) cover one-click Faculty and Student paths and role scope. [Filtered schedule view](../backend/services/schedule_views.py). |
| FR-10.4 | UR-23 | H / shall | List and filter exams | 5 | Verify date/time order and independent date, batch, course and room filters on the exams list. | Verified | [Weekly timetable](../tests/test_timetable.py) and [date-ordered exams](../tests/test_exams.py) opened and filtered in Edge at 360 px with real saved results. |
| FR-10.5 | UR-24 | H / shall | Open own schedule by default | 6 | Log in as two teachers and two students from different batches. Verify published defaults, scope and a path of at most two clicks. | Implemented | [Version browser cases](../tests/test_versions.py) cover one-click Faculty and Student paths and role scope. [Filtered schedule view](../backend/services/schedule_views.py). |
| FR-10.6 | UR-19, UR-20, UR-22 | L / should | Distinguish special entries | 3, 6 | Identify lab blocks, locked entries and overrides in the Coordinator view using text/icon as well as colour. | Implemented | [Version browser cases](../tests/test_versions.py) cover one-click Faculty and Student paths and role scope. [Filtered schedule view](../backend/services/schedule_views.py). |
| FR-10.7 | UR-22 | L / should | Use the dashboard | 1–3, 5, 6 | Check active term, both schedule statuses, appropriate master counts and next-step links before and after generation. | Implemented | [Version browser cases](../tests/test_versions.py) cover one-click Faculty and Student paths and role scope. [Filtered schedule view](../backend/services/schedule_views.py). |
| FR-10.8 | UR-22, UR-23, UR-24 | M / shall | Use views at 360 px | 3, 5 | At 360 px, operate filters, read entries and open actions in both views. An internally scrollable grid keeps page controls reachable. | Verified | [Weekly timetable](../tests/test_timetable.py) and [date-ordered exams](../tests/test_exams.py) opened and filtered in Edge at 360 px with real saved results. |

## FA-11 · Exports · printed pp. 26

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-11.1 | UR-25 | H / shall | Export the displayed PDF | 7 | Parse an A4 landscape PDF and inspect its layout, institution, term, version, filter, generation date and matching records. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |
| FR-11.2 | UR-25 | H / shall | Export the displayed CSV | 7 | Parse UTF-8 with a CSV reader. Check one row per logical session/exam and day, start/end times, course code, session type, instructor, room and batch. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |
| FR-11.3 | UR-25 | M / shall | Produce bulk PDFs | 7 | As Coordinator export all batches and all instructors. Verify each group starts and fits on its own labelled page. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |
| FR-11.4 | UR-24, UR-25 | H / shall | Enforce export scope | 7 | Compare displayed and exported rows. Request another student's scope, hidden version and bulk export without permission and confirm access is denied or scoped. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |
| FR-11.5 | UR-25, UR-26 | L / shall | Audit each export | 7 | Match each successful filtered or bulk download to the correct actor, event time and schedule in the audit log. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |

## FA-12 · Audit · printed pp. 26

| SRS ID | User requirements | Priority / verb | Behaviour | Phase | Acceptance check | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-12.1 | UR-26 | H / shall | Audit important actions | 1–7 | Verify login, failed login, account change, import, config change, generation, manual adjustment, publication and export record actor/time/action/entity. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |
| FR-12.2 | UR-26 | M / shall | Filter admin audit view | 7 | Filter by user, date range and action together. Verify scope, time-zone boundaries and Administrator-only access. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |
| FR-12.3 | UR-26 | H / shall | Keep audit immutable | 1, 7 | Attempt mutation through application roles and verify append-only protections at the storage boundary. Existing history survives account deactivation. | Implemented | [Download and audit evidence](../tests/test_exports.py) and local A4 render. Additional representative grouped, exam and log retention checks remain open. |

## Scheduling rules · Appendix A.5, printed pp. 57–58

Run hard-rule cases with the rule enabled and assert its specific code. Check solver enforcement as well as independent rejection of a crafted schedule. For soft rules, compare candidate scores and repeat at weight zero. Verify configurable rule switches in Phase 4. E03 and H09 also have structural guarantees described in the architecture.

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| H01 | 3 | Instructor exclusivity (mandatory) | Assign the same instructor twice in one slot. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H02 | 3 | Room exclusivity (mandatory) | Assign two classes to one room in one slot. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H03 | 3 | Batch exclusivity (mandatory) | Give two simultaneous classes to one batch. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H04 | 3 | Room capacity | Place an offering in a room one seat too small. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H05 | 3 | Room type | Place a lab in a Lecture room or a lecture in a Lab room. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H06 | 3 | Instructor availability | Use an explicitly unavailable teaching slot. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H07 | 3 | Blocked slot | Place a class across a blocked break. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H08 | 3 | Exact weekly demand (mandatory) | Omit or add a lecture or lab block. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H09 | 3 | Contiguous lab | Split a lab across rooms, days or separated slots. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| H10 | 3 | Teaching-hour limits | Exceed daily and weekly minutes separately, including a non-hourly grid. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| S01 | 3 | Batch gaps | Equal feasible options differ in idle slots on a day. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| S02 | 3 | Offering spread | Compare repeated sessions on one day versus separate days. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| S03 | 3 | Batch sessions per day | Compare schedules at and above the configured daily threshold. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| S04 | 3 | Consecutive teaching slots | Compare runs with and without a sequence above the configured limit. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| S05 | 3 | Stability | Regenerate against a previous version and reward preserved slot/room pairs. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| S06 | 3 | Room fit | With two suitable rooms, score the smallest adequate one higher. | Verified | [Independent rule and preference tests](../tests/test_timetable.py) and valid forced-choice result. |
| E01 | 5 | Shared student (mandatory) | Assign adjacent courses to the same exam session. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| E02 | 5 | Exams per student/day | Exceed the limit across distinct sessions on a single day. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| E03 | 5 | Seat totals and capacity | Under-seat an exam and separately exceed one room's capacity. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| E04 | 5 | Room exclusivity (mandatory) | Allocate a room twice in a session with different exams. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| E05 | 5 | All exam courses once (mandatory) | Leave one course unassigned and separately assign one course twice. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| ES01 | 5 | Batch exam spread | Compare examination days occupied by a batch. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| ES02 | 5 | Few rooms | Compare feasible allocations with equal seats but different room counts. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |
| ES03 | 5 | One building | Compare otherwise identical multi-room allocations across one versus two buildings. | Verified | [Independent exam rule and preference tests](../tests/test_exams.py). |

## Performance · §4.1, printed p. 39

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| P-1 | 8 | Ordinary pages and API | On A-1/minimum platform measure p95 ≤2 s for ordinary pages, lists, filters and forms at up to 50 concurrent users. | In progress | [50-user HTTPS rehearsal](LOCAL_VERIFICATION.md#performance-on-this-host) found SQLite p95 above target. Minimum deployment profile and mixed operations remain open. |
| P-2 | 8 | Timetable generation | On A-1 measure the configured bound (default 120 s), best feasible result found in budget and the typical ≤60 s target. | Implemented | [Engine-only reference and doubled measurements](LOCAL_VERIFICATION.md#performance-on-this-host). Release end-to-end and minimum-profile measurements pending. |
| P-3 | 8 | Exam generation | On A-1 with up to 80 exam courses measure end-to-end graph, colouring and allocation ≤30 s. | Implemented | [Engine-only reference and doubled measurements](LOCAL_VERIFICATION.md#performance-on-this-host). Release end-to-end and minimum-profile measurements pending. |
| P-4 | 6, 8 | Immediate validation | Measure manual moves from submission to validation response ≤1 s, including rejected class and exam moves. | Implemented | [Small fixture and CSV rehearsal timing](LOCAL_VERIFICATION.md#performance-on-this-host). Reference-profile measurements pending. |
| P-5 | 4, 8 | CSV throughput | Read, validate and import 5,000 rows in ≤15 s. Record phase timings and total. | Implemented | [Small fixture and CSV rehearsal timing](LOCAL_VERIFICATION.md#performance-on-this-host). Reference-profile measurements pending. |
| P-6 | 7, 8 | Export latency | Single schedule PDF and CSV each ≤5 s. All batches in one PDF ≤30 s. | Implemented | [Small fixture and CSV rehearsal timing](LOCAL_VERIFICATION.md#performance-on-this-host). Reference-profile measurements pending. |
| P-7 | 8 | Schedule queries | Time underlying view queries on A-1 with intended indexes. Each ≤500 ms. | Implemented | Reference SQLite query and view shaping measured 7.5 ms on the development host. [Rehearsal](LOCAL_VERIFICATION.md#performance-on-this-host). |
| P-8 | 8 | Worker isolation | Repeat identical ordinary request load with worker idle and solving. Compare like-for-like latencies with ≤20% degradation. | In progress | [Idle and active 50-user rehearsals](LOCAL_VERIFICATION.md#performance-on-this-host) show variable relative p95. Target deployment evidence is pending. |

## Safety · §4.2.1, printed p. 40

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| SAF-1 | 6 | Validate at publish | Corrupt a candidate in a fixture after review and verify fresh validation rejects publication. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| SAF-2 | 3, 5 | Transactional results | Inject failure mid-write, request cancel and timeout. Check rollback, prior versions and zero partial entries for both generators. | Implemented | Worker, timeout, queued cancellation and stale-lease cases in [test_timetable.py](../tests/test_timetable.py). Live in-search cancellation and injected persistence failure remain ahead of release. |
| SAF-3 | 2–6 | Confirm consequential operations | Cancel and confirm in-use deactivation, disabling a hard rule, discarding a version and replacing a publication. Name the actual consequence. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| SAF-4 | 6 | Immutable publication | Reject in-place edits to Published and Archived, duplicate to change and reapprove. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |
| SAF-5 | 8 | Automatic daily backup | Configure at least daily backups retaining the latest seven. Exercise rotation over eight runs and restore master data and schedules to a clean database. | Implemented | [SQLite restore and seven-copy retention](../tests/test_backups.py) and [PostgreSQL recovery](../tests/test_schema.py) passed. Institutional scheduling remains open. |
| SAF-6 | 6 | Recover earlier publication | Open original archive and restore its content via a new validated, approved version. Verify the old versions remain. | Implemented | [Guarded version cases](../tests/test_versions.py), [rule tests](../tests/test_timetable.py) and PostgreSQL source/destination trigger. Complete full adjustment, corrupt publication and retention gates. |

## Security · §4.2.2, printed pp. 40–41

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| SEC-1 | 1 | Authentication | Only login and its required static assets are public. Require credentials and ≥8-character passwords. | Verified | [Credential and session checks](../tests/test_access.py) and [Edge login](../tests/test_browser.py). |
| SEC-2 | 1 | Password storage | Inspect authorised test database, API representations and logs for salted bcrypt ≥12 and absence of plaintext or exposed hashes. | Verified | [Credential and session checks](../tests/test_access.py) and [Edge login](../tests/test_browser.py). |
| SEC-3 | 1–7 | Authorisation | For each new operation check server role and object scope, including hidden detail and download routes. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |
| SEC-4 | 1 | Sessions and lockout | Clock-controlled tests verify 30-minute inactivity, five consecutive failures and 15-minute lock. | Verified | [Credential and session checks](../tests/test_access.py) and [Edge login](../tests/test_browser.py). |
| SEC-5 | 1, 8 | TLS transport | Test actual browser endpoint on TLS 1.2+ and refusal/redirect of HTTP. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |
| SEC-6 | 1–7 | Input and output handling | Check server-side types/ranges, ORM bound parameters and safe output encoding for user-supplied text. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |
| SEC-7 | 4 | CSV uploads | Exercise type/10 MB boundary, data-only parser and temp files outside the web root. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |
| SEC-8 | 1, 8 | Privileges and secrets | Review restricted runtime DB rights, separate migration credentials, and environment-supplied secrets absent from tracked files. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |
| SEC-9 | 1, 7 | Accountability | Verify listed security events reach an append-only trail including unknown-user login attempts. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |
| SEC-10 | 1, 6 | Privacy | Check minimal name/email/role/links, own-batch Published results for Students and Published-only scope for Faculty. | Implemented | [Local security evidence and deployment gaps](LOCAL_VERIFICATION.md). Hosted grants were inspected from the dated catalog. |

## Database · §5.1, printed pp. 44–53

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| DB-1 | 1–7 | Relational business data | Compare migrations against all 21 table specifications in §5.1.3, including every column/type/default and supporting data needed to reproduce versions. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-2 | 2, 3, 5 | Third normal form | Review functional dependencies. Verify copied instructor_id and batch_id on timetable entries agree with the offering and enforce clash uniqueness. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-3 | 1–7 | Keys and relationships | Inspect each named single integer surrogate PK and every FK in column specs and Table 30. Attempt orphan writes on both databases. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-4 | 1–7 | Database constraints | Reject invalid NULL, uniqueness and CHECK values directly at persistence, including a blocked slot without a reason. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-5 | 2, 4, 7 | Retention | Test referenced-record deactivation, immutable schedule history and append-only audit and import logs. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-6 | 3, 5 | One result transaction | Inject a write failure after candidate entries/room allocations and before final status. Confirm complete rollback. | Implemented | Worker, timeout, queued cancellation and stale-lease cases in [test_timetable.py](../tests/test_timetable.py). Live in-search cancellation and injected persistence failure remain ahead of release. |
| DB-7 | 3, 5, 8 | Indexes | Inspect each FK and entry lookup index for schedule, slot, room and instructor. Check query plans and P-7. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-8 | 1–7 | UTF-8 and event time | Round-trip Urdu names and UTC event timestamps. Render local Asia/Karachi dates/times and verify boundary dates. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |
| DB-9 | 1–8 | Versioned migrations | Apply migrations from empty and prior-phase databases on PostgreSQL and SQLite, compare constraints, FK enforcement and behaviour. | Implemented | [SQLite constraints and PostgreSQL 17.11 catalog/runtime](../tests/test_schema.py). Supporting composite index was added locally. Release role, query and recovery checks remain open. |

## Design constraints and assumptions · §§2.4–2.7, printed pp. 10–13

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| C-1 | 1, 3, 5 | Open-source stack | Inspect pinned Python/OR-Tools/NetworkX and React/Tailwind stack and licence inventory. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| C-2 | 1–7 | Web/REST | Drive actual browser workflows through the HTTPS REST/JSON API. Exercise business rules independently of React. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| C-3 | 1, 8 | Two databases | Change only connection settings to run the SQLAlchemy-backed system on SQLite ≥3.35 and PostgreSQL ≥15. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| C-4 | 3, 5, 8 | Bounded runs | Share a wall-clock budget across search, fallback and allocation. Record actual elapsed time, best candidate or reason. | Planned | — |
| C-5 | 1, 8 | Secure transport and access | Verify hashes, encryption in transit and per-request authorisation on the deployed profile. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| C-6 | 2, 3 | Weekly grid | Generate equal whole slots, default 60 minutes, recurring weekly and contiguous lab blocks. | Planned | — |
| C-7 | 1–8 | Semester, four students, free tools | Keep delivery within Table 1. Phase reviews confirm open-source tools and the planned single-department scope. | Planned | — |
| C-8 | 1–8 | SRS conventions | Preserve original LaTeX-produced PDF, exact identifiers and UML 2.x convention for any maintained behavioural model. | Planned | — |
| C-9 | 8 | Browser compatibility | Release check in current Chrome, Firefox, Edge and Safari, without plug-ins. | Planned | — |
| A-1 | 8 | Reference dataset | One institution, up to 40 batches, 150 offerings, 80 instructors, 60 rooms, 6 × 8 slots and 3,000 enrolled students. Include up to 80 exam courses for §4.1. | Planned | — |
| A-2 | 2, 3 | Offering model | Exactly one instructor and batch per offering, with known weekly contact hours before solving. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| A-3 | 2, 4 | Input quality | Validate format and internal consistency. Describe institutional responsibility for factual accuracy in help. | Planned | — |
| A-4 | 2, 5 | Optional explicit enrollments | Check explicit elective/repeat clashes and batch-wide fallback on distinct fixtures. Identify partial or inconsistent rosters. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| A-5 | 2, 3 | Equal slots and breaks | Model lunch/prayer as blocked slots on that term's grid. Inspect sample timetable for respected breaks. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |
| A-6 | 1, 8 | Network and browser | Document reachable server/current browser as prerequisites. Test supported clients on the institutional HTTPS profile. | Planned | — |
| A-7 | 2, 3 | Weekly repetition | Use the same timetable week to week within a term. Keep dated sessions for exams. | Implemented | [Local startup and stack](../README.md) and [verification results](LOCAL_VERIFICATION.md). |

## Quality attributes · §4.3, printed pp. 41–43

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| §4.3.1 | 3, 5, 8 | Correctness | Zero enabled hard violations on every accepted fixture including A-1. Dedicated independent-validator negative case for each H01–H10 and E01–E05. | Planned | — |
| §4.3.2 | 3, 5, 8 | Reliability | Measure ≥99% valid-input generations without internal error, record reasons. Restart during generation and check Infeasible/interrupted with no partial output. | Planned | — |
| §4.3.3 | 8 | Availability | Measure ≥99% monthly availability 08:00–18:00 on working days. Check maintenance scheduling outside these hours. Distinguish measured months from instrumentation drills. | Implemented | [HTTPS monitoring and month report](OPERATIONS.md). Empty log correctly produces no availability percentage. Deployed month remains pending. |
| §4.3.4 | 4, 6, 8 | Usability | Fresh coordinator using the two-page guide goes imported data → generated timetable unaided in <15 min. Faculty and Students find own timetable within two clicks. Verify actionable errors, icons/text and AA contrast. | Planned | — |
| §4.3.5 | 3, 5, 7, 8 | Maintainability | One discoverable class and database rule row per rule, independent validation, separate layers, configurable parameters, one class per exporter, PEP 8/docstrings, pinned deps and ≥70% automated unit coverage of engine and validator. | In progress | [Engine and validator coverage](evidence/engine-coverage.txt) reached 82% overall. Separate rule classes and more exam solver branches remain open. |
| §4.3.6 | 8 | Portability | One-command startup, Linux and Windows, both supported DBs, current Chrome/Firefox/Edge/Safari. | Planned | — |
| §4.3.7 | 3, 5, 8 | Testability | Deliver sample data with expected results, repeatable seed/config and a test/evidence link for every requirement. | Planned | — |
| §4.3.8 | 1, 4, 7 | Interoperability | Verify UTF-8 CSV, JSON with OpenAPI, printable PDF and matching content types. | Planned | — |
| §4.3.9 | 2, 4, 6 | Adaptability | Create a new term, room or break without code changes, reuse previous configuration and verify historical schedules. | Planned | — |
| §4.3.10 | 1, 3, 7 | Flexibility | Review seams for a new rule + row, exporter class or role/access policy change without redesign. Preserve the five SRS roles in this release. | Planned | — |
| §4.3.11 | 3–6 | Robustness | Reject malformed rows individually, report invalid/infeasible data, preserve earlier versions on cancel/timeout. | Planned | — |
| §4.3.12 | 3, 4, 5, 7 | Reusability | Invoke engine, validator and CSV components without web imports. Document schema and templates for another department. | Planned | — |
| §4.3.13 | 8 | Scalability | Run with twice the reference offerings and rooms (300/120) and verify bounded search without architecture changes. | Planned | — |

## Interfaces, documentation and data dictionary · source sections as listed

| SRS reference | Phase | Subject | Acceptance check or fixture | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| §1.2.1 / Table 1 | 1–8 | Release boundaries | Review features against the in-scope column. Exclude registration/fees/grades/attendance, ERP/SIS, invigilation/seat numbers, multi-campus travel, native apps, notifications, co-teaching and payments/procurement. | Planned | — |
| §1.5.3 / §5.3 | 1–8 | Names and localisation | Separate English text resources, UTF-8 Urdu names, 24-hour time, DD/MM/YYYY, Asia/Karachi and configurable first weekday. Check SRS table, course and seat naming conventions. | Planned | — |
| §2.4 / Table 6 | 1, 8 | Minimum platform | Check client ≥360 px and 1280 px entry layout. Target 2 cores/4 GB/10 GB free, 4 cores/8 GB recommended. Ubuntu 22.04+ and Windows 10/11, Python ≥3.11, Node ≥18 for build only, HTTPS port 443. | Planned | — |
| §2.6 | 4, 7, 8 | Delivered user documentation | Open two-page data-to-publication quick start, role manual PDF with screenshots and four chapters, installation/admin guide PDF, per-screen help and per-field tooltips, six CSV templates with samples and field guides, and interactive OpenAPI. | Planned | — |
| §3.1.1 / Table 7 | 1–7 | Twelve screens and GUI standards | Visit Login, Dashboard, Master Data, Import Wizard, Availability, Constraints and Settings, Generate, Timetable View, Exam Schedule View, Conflict Report, Review and Publish, Users and Audit Log. Check aligned primary action with adjacent Cancel, consequence confirmation, red inline and summary errors, fixed icon/text status area, 25-row default, visible labels/tooltips, WCAG 2.1 AA contrast and ≥360 px. | Planned | — |
| §3.1.2 | 7, 8 | Hardware interface | Complete tasks with standard browser input including touch/keyboard. Print exported PDF through ordinary OS/browser print. | Planned | — |
| §3.1.3 / Table 8 | 1, 3, 5, 7 | Software interfaces | Inspect environment configuration, temp upload/export working directory, file logs, separate worker and database-only data sharing. Verify pinned server, solver, ORM, PDF and graph dependencies. | Planned | — |
| §3.1.4 / Table 9 | 1–7 | Communications | Verify documented methods/paths, HTTPS ≥TLS 1.2, restricted origin, JWT Authorization header, UTF-8 JSON, multipart ≤10 MB, export MIME types, two-second polling and encrypted or local database connection. | Planned | — |
| §3.3.2–4 / Figures 7–13 / Table 26 | 3, 5, 6 | Interaction and state models | Test accepted/refused request and state paths against the architecture lifecycle, timetable/exam order, edit refusal and publication response. | Planned | — |
| §5.1.4–5 / Table 30 | 2, 3, 5, 6 | Relational integrity | Check every FK, one active term at most, uniqueness of slot resources and exam course, exact seat sums, role links, one publication per term/type, immutable Published/Archived entries. | Planned | — |
| §5.2 | 7, 8 | Privacy and licences | Document applicable university data-handling rules, map protection of staff/student records to SEC-10 and deliver notices for all pinned third-party packages. Record outstanding institutional review if rules are unavailable. | Planned | — |
| §5.4 | 7, 8 | Reuse objectives | Adopt sample templates and documented database schema for a second synthetic departmental dataset without web-layer changes. | Planned | — |
| Appendix A.1 | 1–8 | Configuration constants | Check all 16 settings against the appendix, including default max exams/day 2, batch sessions/day 5, instructor consecutive slots 3, 25 rows, 2 s poll and seven daily backups. | Planned | — |
| Appendix A.2 | 1–6 | State values | Check all listed account, term, solver, schedule, room, session, severity, flag and role values through schema and fixtures. | Planned | — |
| Appendix A.3–4 | 1–7 | Inputs and outputs | For each named input/output, exercise its actor, validation, persistence, recipient and display/file shape through its phase workflow. | Planned | — |

## Database baseline for the existing Supabase project

**Inspected 21 November 2026.** The connected ATES-DB project runs PostgreSQL 17.11 with UTF8 encoding and UTC as its default time zone. Its public schema contains all 21 SRS tables, 146 columns and all 36 scalar foreign keys in §5.1.3. An additional composite FK verifies the instructor and batch copied from an offering into timetable entries. The schema has 83 indexes and seven application triggers. The Supabase migration listing returned zero entries. Existing schema objects are the baseline for local reproduction. [Read-only catalog snapshot](SUPABASE_CATALOG.json)

The last column records catalog evidence and remaining checks. Each relation is in the public schema. Presence of a trigger or constraint is evidence of its definition. Transaction behaviour, role permissions in a running application, historical data and performance still require tests on disposable databases. DB-1 through DB-9 keep their release status until those checks pass.

| SRS §5.1.3 item | Required relation | Examples of checks on the existing database | Feature phase | Hosted evidence / gap |
| --- | --- | --- | --- | --- |
| 1 | `public.departments` | Integer department_id, unique code, required name. | 1 | Identity PK, unique code and required name match. |
| 2 | `public.academic_terms` | Unique name, start/end ordering, Planned/Active/Closed and at most one Active. | 2 | Dates and three statuses checked. Partial unique index limits Active to one. |
| 3 | `public.time_slots` | FK term, unique term/day/index, ordered times and required reason on a blocked slot. | 2 | Term FK, unique (term_id, day_of_week, slot_index), valid day/index/time and nonblank block reason. Test repeat-save behaviour in the application. |
| 4 | `public.batches` | FK department, unique programme/year/section, positive strength and active flag. | 1–2 | Department FK, unique programme/year/section, positive strength and active flag match. |
| 5 | `public.courses` | Unique code, FK department, nonnegative credits/hours, positive combined lecture/lab hours. | 2 | Department FK, unique code, hour/credit ranges, positive total contact hours and active flag match. |
| 6 | `public.instructors` | FK department, unique email, positive daily limit, weekly ≥ daily, active flag. | 1–2 | Department FK, unique email, daily/weekly bounds and defaults 4/18 match. |
| 7 | `public.instructor_availability` | FKs instructor and slot, unique instructor/slot pair and available default. | 2 | Both FKs, unique instructor/slot and default true match. |
| 8 | `public.rooms` | Unique code, required building, positive capacity, specified type and active flag. | 2 | Unique code, positive capacity, three allowed room types and active flag match. |
| 9 | `public.users` | Unique username/email, salted hash, five roles, status/lock fields, unique faculty link, student batch link and event time. | 1 | Five roles, Faculty/Student link checks, unique username/email/instructor and lockout fields exist. No FK to auth.users in this table. Verify credentials, session lifecycle and RBAC in the application. |
| 10 | `public.course_offerings` | FKs term/course/batch/instructor, positive count, unique term/course/batch. | 2 | All four FKs, positive count, unique term/course/batch and extra offering/instructor/batch key exist. |
| 11 | `public.enrollments` | FK offering and FK student to users, Student role, unique offering/student. | 2 | Both FKs and unique offering/student exist. The user FK alone does not enforce the Student role. Check role at the service boundary. |
| 12 | `public.scheduling_configs` | FKs term and creator, schedule type, unique term/type/name, bound time limit and seed. | 2–4 | Term/creator FKs, unique name by scope, 10–600 s limit and 120/1 defaults. Invoke rule initialisation explicitly on local setup. |
| 13 | `public.constraint_rules` | FK config, unique config/rule code, type, enabled, soft weight 0–10 and integer parameter. | 2–4 | Unique code per config, Hard/Soft type, 0–10 weights and all seven mandatory-enable guards exist. The seed function defines all 24 codes. Seeded rows were not inspected. |
| 14 | `public.schedules` | FKs term, config and generator/approver, six states, solver stats, unique term/type/version and single Published per term/type. | 3, 6 | All four FKs, six states, numeric precision/scale, positive version, unique term/type/version and one Published per term/type. Verify transitions, worker ownership and atomic publication in application tests. |
| 15 | `public.timetable_entries` | FKs version/offering/instructor/batch/room/slot, one row per occupied slot, three independent clash uniqueness constraints, lock/override flags. | 3, 6 | Three clash keys, lock/override flags and all six scalar FKs exist. Extra composite FK enforces copied offering values. DB-7 retains one composite-index gap. |
| 16 | `public.exam_slots` | FK term, valid date/time window, label, unique term/date/start and overlap check. | 4 | Unique term/date/start, time ordering and overlap trigger exist. Verify simultaneous inserts on a disposable database. |
| 17 | `public.exam_entries` | FKs schedule/course/exam slot, positive count, lock and unique course per version. | 5, 6 | Course/session/version FKs, unique course per version, positive count and lock present. Plan persisted manual-override support for FR-8.5. |
| 18 | `public.exam_room_allocations` | FKs exam entry/room, unique pair, positive seats bounded by room capacity, per-session exclusivity. | 5 | Room/entry FKs, unique pair, positive seats and per-allocation capacity trigger present. Validate total seats and room exclusivity per session across exams. |
| 19 | `public.conflict_log` | FK schedule, type and severity, description, entity reference, time and resolution flag. | 3, 5 | Schedule FK, Hard/Warning severity, description, entity reference, time and resolved flag present. |
| 20 | `public.import_logs` | FK user, entity type, filename, total/imported/rejected counts, time and append-only history. | 4 | User FK, nonnegative row counts and UPDATE/DELETE protection present. Review effective table-wide privileges for retention. |
| 21 | `public.audit_logs` | Nullable FK user for unknown-user failures, action, entity, details, time and append-only history. | 1, 7 | Nullable user FK, action/entity/time fields and UPDATE/DELETE protection present. Review effective table-wide privileges for retention. |

### Phase 1 follow-up from the hosted catalog

- **Database access.** All 21 tables have RLS enabled and zero policies. The ordinary Supabase roles have broad table grants, including TRUNCATE. PostgreSQL's default row policy denies ordinary row access without an applicable policy. Table-wide TRUNCATE is outside that protection. The observed service role bypasses RLS. Test a dedicated least-privilege API/worker role on a disposable copy and keep the application behind FastAPI. Review Data API exposure and real runtime-role grants before deployment. No external endpoint or user identity was exercised. [PostgreSQL row security](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)
- **Integrity and history.** Preserve both partial unique indexes, the three timetable clash keys and the blocked-slot check. Append-only triggers cover UPDATE and DELETE. Treat protecting log retention against table-wide operations as a privilege requirement. Test both the source and destination version on entry edits to protect published history. Verify exam-session overlap under simultaneous writes and validate seat totals and exclusive room use independently.
- **Index and baseline.** Single-column FK indexes cover all SRS relationships. The additional composite FK on timetable_entries has no child-side index starting with its three columns together. Rehearse a supporting index and collect P-7 timings locally. Reconstruct a versioned baseline from existing definitions and validate restoration before proposing any hosted migration.
- **Scope.** This catalog review inspected metadata, including application trigger and function definitions. Account data, enrollment data, stored rule instances, backup recovery, provider Auth configuration and live API permissions remain untested.
