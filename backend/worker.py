"""Claim and solve timetable jobs outside the web process."""

from datetime import timedelta
import logging
import os
import sys
from threading import Event, Thread
from time import monotonic
from uuid import uuid4

from sqlalchemy import or_, select

from backend.data.store import Store
from backend.engine.exam_validator import exam_objective, validate_exams
from backend.engine.exam_data import ExamProblem
from backend.engine.exams import solve_exams
from backend.engine.timetable import solve
from backend.engine.timetable_data import Timetable
from backend.engine.validator import objective, validate
from backend.services.scheduling import end_run, get_schedule
from backend.services.security import utc_now

HEARTBEAT = 2
LEASE = timedelta(seconds=12)
logger = logging.getLogger(__name__)


def claim(store):
    schedules = store["schedules"]
    runs = store["schedule_runs"]
    with store.transaction() as connection:
        now = utc_now()
        active = select(schedules.c.schedule_id, schedules.c.generated_by, runs.c.started_at).join(runs).where(
            schedules.c.status == "Generating",
        )
        stale = active.where(runs.c.claim_id.is_not(None), or_(
            runs.c.heartbeat_at.is_(None), runs.c.heartbeat_at <= now - LEASE,
        )).with_for_update(of=schedules, skip_locked=True)
        for key, actor, started in connection.execute(stale):
            end_run(connection, store, key, "interrupted", "The worker stopped before saving a result.", actor,
                    seconds=(now - started).total_seconds() if started else 0)
        queued = active.where(runs.c.claim_id.is_(None)).order_by(schedules.c.schedule_id).limit(1)
        row = connection.execute(queued.with_for_update(of=schedules, skip_locked=True)).first()
        if not row:
            return None
        key, actor, _ = row
        owner = str(uuid4())
        snapshot = connection.scalar(runs.update().where(runs.c.schedule_id == key).values(
            claim_id=owner, started_at=now, heartbeat_at=now,
        ).returning(runs.c.input_snapshot))
        return key, owner, actor, snapshot


class RunCancellation:
    def __init__(self, store, key, owner, stopping):
        self.store = store
        self.key = key
        self.owner = owner
        self.stopping = stopping
        self.finished = Event()
        self.cancelled = Event()
        self.solver = None
        self.thread = Thread(target=self.monitor, name="solver-heartbeat", daemon=True)

    def __call__(self):
        return self.cancelled.is_set() or self.stopping.is_set()

    def bind(self, solver):
        self.solver = solver

    def monitor(self):
        while not self.finished.wait(HEARTBEAT):
            try:
                with self.store.transaction() as connection:
                    schedule, run = get_schedule(connection, self.store, self.key, lock=True)
                    if schedule["status"] == "Generating" and run["claim_id"] == self.owner and not self.stopping.is_set():
                        table = self.store["schedule_runs"]
                        connection.execute(table.update().where(table.c.schedule_id == self.key)
                                           .values(heartbeat_at=utc_now()))
                        continue
            except Exception:
                logger.exception("Could not renew schedule %s.", self.key)
            self.cancelled.set()
            if self.solver is not None:
                self.solver.stop_search()
            return

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.finished.set()
        self.thread.join()


def run_once(store, stopping, solver=solve):
    job = claim(store)
    if job is None:
        return False
    key, owner, actor, frozen = job
    started = monotonic()
    candidate, score, defects = None, None, []
    statistics = None
    with RunCancellation(store, key, owner, stopping) as cancel:
        try:
            exam = frozen.get("type") == "Exam"
            problem = ExamProblem(frozen) if exam else Timetable(frozen)
            engine = solve_exams if exam else solver
            result = engine(problem, frozen["time_limit"], frozen["seed"], cancel)
            status, reason = result.status, result.reason
            if exam:
                statistics = {
                    "courses": len(problem.courses), "sessions_used": len({entry.slot for entry in result.assignments}),
                    "rooms_used": len({room for entry in result.assignments for room in entry.rooms}),
                    "dsatur_colors": result.colors, "exact_fallback": result.fallback,
                }
            if status in {"optimal", "feasible"}:
                defects = (validate_exams if exam else validate)(problem, result.assignments)
                if defects:
                    status, reason = "interrupted", "The independent validator rejected the proposed schedule."
                else:
                    candidate = result.assignments
                    score = (exam_objective if exam else objective)(problem, candidate)
        except Exception:
            logger.exception("Timetable generation failed for schedule %s.", key)
            status, reason = "interrupted", "An internal error interrupted generation."
        if cancel():
            status, reason = "interrupted", "The worker stopped before saving a result."
            candidate, score = None, None
    elapsed = monotonic() - started
    try:
        finish(store, key, owner, actor, status, reason, elapsed, candidate, score, defects, statistics)
    except Exception:
        logger.exception("Could not commit results for schedule %s.", key)
        finish(store, key, owner, actor, "interrupted", "The result could not be saved.", elapsed, None, None, ())
    return True


def finish(store, key, owner, actor, status, reason, elapsed, candidate, score, defects, statistics=None):
    with store.transaction() as connection:
        schedule, run = get_schedule(connection, store, key, lock=True)
        if schedule["status"] != "Generating" or not run or run["claim_id"] != owner:
            return
        end_run(connection, store, key, status, reason, actor, seconds=elapsed,
                assignments=candidate, score=score, defects=defects, statistics=statistics)


def work(url, stopping):
    logging.basicConfig(level=logging.INFO)
    store = Store(url)
    logger.info("Solver worker %s is ready.", os.getpid())
    try:
        while not stopping.is_set():
            try:
                if not run_once(store, stopping):
                    stopping.wait(1)
            except Exception:
                logger.exception("The worker could not process a job.")
                stopping.wait(2)
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    stopping = Event()
    if os.getenv("ATES_WORKER_STDIN") == "1":
        def stop_on_eof():
            sys.stdin.buffer.read()
            stopping.set()

        Thread(target=stop_on_eof, daemon=True).start()
    try:
        work(os.environ["ATES_DATABASE_URL"], stopping)
    except KeyboardInterrupt:
        pass

