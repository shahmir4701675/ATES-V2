"""Rehearse reference-sized HTTPS view traffic with an idle and active solver worker."""

import asyncio
import argparse
from datetime import date, time
from pathlib import Path
from time import perf_counter, sleep
from uuid import uuid4
import json
import os

import httpx

from backend.api.schedules import ScheduleFilters
from backend.cli import LOCAL
from backend.data.database import check_disposable, database
from backend.data.migrate import migrate
from backend.data.store import Store
from backend.services.accounts import insert
from backend.services.schedule_views import filtered_view
from backend.services.scheduling import get_schedule
from backend.services.security import password_hash
from sqlalchemy import select
from examples.reference_benchmark import teaching
from test_browser import running_server

SECRET = "benchmark-account-only"


def populate(store):
    reference = teaching(1)
    with store.transaction() as connection:
        department = insert(connection, store["departments"], {"code": "CS", "name": "Computing"})["department_id"]
        terms = store["academic_terms"]
        term = insert(connection, terms, {"name": "Reference", "start_date": date(2027, 1, 1),
                      "end_date": date(2027, 5, 1), "status": "Active"})["term_id"]
        coordinator = insert(connection, store["users"], {"username": "reference", "email": "reference@example.test",
                             "full_name": "Reference Coordinator", "role": "Coordinator",
                             "password_hash": password_hash(SECRET)})["user_id"]
        users = store["users"]
        connection.execute(users.insert(), [{
            "username": f"reader{i}", "email": f"reader{i}@example.test", "full_name": f"Reader {i}",
            "role": "Approver", "password_hash": password_hash(SECRET),
        } for i in range(50)])
        connection.execute(store["rooms"].insert(), [
            {**{key: value for key, value in room.items() if key != "room_id"}, "room_code": f"R{room['room_id']:03}"}
            for room in reference["rooms"]
        ])
        connection.execute(store["batches"].insert(), [
            {"department_id": department, "program_code": f"B{i:02}", "batch_year": 2027, "section": "A", "strength": 75}
            for i in range(1, 41)
        ])
        connection.execute(store["instructors"].insert(), [
            {"department_id": department, "full_name": f"Instructor {i}", "email": f"faculty{i}@example.test"}
            for i in range(1, 81)
        ])
        connection.execute(store["courses"].insert(), [
            {"department_id": department, "course_code": f"CS{row['offering_id']:03}",
             "title": f"Reference course {row['offering_id']}", "credit_hours": 3,
             "lecture_hours": row["lecture_slots"], "lab_hours": row["lab_slots"]}
            for row in reference["offerings"]
        ])
        connection.execute(store["course_offerings"].insert(), [
            {"term_id": term, "course_id": row["offering_id"], **{key: row[key] for key in ("batch_id", "instructor_id", "enrolled_count")}}
            for row in reference["offerings"]
        ])
        connection.execute(store["time_slots"].insert(), [
            {"term_id": term, "day_of_week": row["day_of_week"], "slot_index": row["slot_index"],
             "start_time": time.fromisoformat(row["start_time"]), "end_time": time.fromisoformat(row["end_time"]),
             "is_blocked": row["is_blocked"], "block_reason": "Break" if row["is_blocked"] else None}
            for row in reference["slots"]
        ])
        from backend.services.rules import default_config
        config = default_config(connection, store, coordinator, term, "Timetable")
        table = store["scheduling_configs"]
        connection.execute(table.update().where(table.c.config_id == config).values(solver_time_limit_s=45))
    return term


def authorize(client, username):
    response = client.post("/auth/login", json={"username": username, "password": SECRET})
    response.raise_for_status()
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def new_run(client, headers, term):
    response = client.post("/schedules/generate", headers=headers, json={
        "term_id": term, "request_token": str(uuid4()),
    })
    response.raise_for_status()
    assert response.status_code == 202, response.json()
    return response.json()["schedule_id"]


def await_phase(client, headers, key, accept, max_wait=55):
    deadline = perf_counter() + max_wait
    while perf_counter() < deadline:
        response = client.get(f"/schedules/{key}/status", headers=headers)
        response.raise_for_status()
        status = response.json()
        if accept(status):
            return status
        if status["status"] != "Generating":
            raise RuntimeError(status)
        sleep(.4)
    raise TimeoutError("The worker did not reach the requested phase.")


async def wave(url, key, sessions):
    async with httpx.AsyncClient(base_url=url, verify=False, timeout=10,
                                 limits=httpx.Limits(max_connections=60, max_keepalive_connections=60),
                                 trust_env=False) as client:
        warmed = await asyncio.gather(*(client.get("/") for _ in sessions))
        assert all(response.status_code == 200 for response in warmed)
        async def sample(headers):
            started = perf_counter()
            try:
                result = await client.get(f"/schedules/{key}/entries", headers=headers)
                status = result.status_code
            except httpx.TransportError:
                status = 0
            return status, perf_counter() - started

        results = await asyncio.gather(*(sample(session) for session in sessions))
    samples = sorted(elapsed for _, elapsed in results)
    return {"requests": len(results), "ok": sum(status == 200 for status, _ in results),
            "p95": round(samples[int(.95 * len(samples) + .999) - 1], 4), "worst": round(samples[-1], 4),
            "samples": [round(item, 4) for item in samples]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="Reuse a database generated by this rehearsal.")
    args = parser.parse_args()
    postgres_url = os.getenv("ATES_TEST_DATABASE_URL")
    if args.fixture and postgres_url:
        raise ValueError("Choose either a SQLite fixture or a fresh disposable PostgreSQL database.")
    evidence = LOCAL / "evidence" / ("reference-http-postgres" if postgres_url else "reference-http")
    evidence.mkdir(parents=True, exist_ok=True)
    db_path = args.fixture.resolve(strict=True) if args.fixture else LOCAL / ("reference-http-" + uuid4().hex + ".sqlite3")
    if not db_path.is_relative_to(LOCAL) or not db_path.name.startswith("reference-http-"):
        raise ValueError("Use a synthetic reference-http database under .ates.")
    url = postgres_url or f"sqlite:///{db_path.as_posix()}"
    check_disposable(url)
    engine = database(url)
    migrate(engine)
    engine.dispose()
    store = Store(url)
    try:
        if args.fixture:
            with store.engine.connect() as connection:
                terms = store["academic_terms"]
                term = connection.scalar(select(terms.c.term_id).where(terms.c.name == "Reference"))
                schedules = store["schedules"]
                existing = connection.scalar(select(schedules.c.schedule_id).where(
                    schedules.c.term_id == term, schedules.c.status == "Generated",
                ).order_by(schedules.c.schedule_id.desc()).limit(1))
        else:
            term = populate(store)
            existing = None
        with running_server(url, evidence, worker=True) as address, httpx.Client(
            base_url=address, verify=False, timeout=15, trust_env=False
        ) as client:
            coord = authorize(client, "reference")
            readers = [authorize(client, f"reader{key}") for key in range(50)]
            key = existing or new_run(client, coord, term)
            status = await_phase(client, coord, key, lambda row: row["status"] == "Generated")
            print(json.dumps({"phase": "generation", "elapsed": float(status["run_seconds"]),
                              "score": float(status["objective_score"]), "solver": status["solver_status"]}), flush=True)
            with store.engine.connect() as connection:
                schedule, details = get_schedule(connection, store, key)
                started = perf_counter()
                payload = filtered_view(connection, store, {"role": "Approver"}, schedule, details, ScheduleFilters())
                assert len(payload["entries"]) == 180
                print(json.dumps({"phase": "local_view_query", "seconds": round(perf_counter() - started, 4),
                                  "entries": len(payload["entries"])}), flush=True)
            client.get(f"/schedules/{key}/entries", headers=readers[0]).raise_for_status()
            idle = asyncio.run(wave(address, key, readers))
            print(json.dumps({"phase": "worker_idle", **idle}), flush=True)
            live = new_run(client, coord, term)
            await_phase(client, coord, live, lambda row: row["phase"] == "Solving")
            busy = asyncio.run(wave(address, key, readers))
            result = client.get(f"/schedules/{live}/status", headers=coord).json()
            print(json.dumps({"phase": "worker_solving", "still_solving": result["phase"] == "Solving",
                              "p95_change_percent": round((busy["p95"] / idle["p95"] - 1) * 100, 2), **busy}), flush=True)
            client.post(f"/schedules/{live}/cancel", headers=coord).raise_for_status()
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()

