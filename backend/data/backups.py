"""Atomic local backups, seven-copy retention and fresh-target recovery."""

from contextlib import closing
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from threading import Event, Thread
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, make_url

from backend.data.database import check_disposable, database

KARACHI = ZoneInfo("Asia/Karachi")
KEEP = 7
PREFIX = "ates-backup-"
LOG = logging.getLogger(__name__)


def pg_command(target, command, args):
    bin_dir = os.getenv("ATES_PG_BIN")
    executable = str(Path(bin_dir) / (command + (".exe" if os.name == "nt" else ""))) if bin_dir else shutil.which(command)
    if not executable:
        raise RuntimeError(f"Install PostgreSQL client tools or configure ATES_PG_BIN to run {command}.")
    env = dict(os.environ, PGHOST=target.host, PGPORT=str(target.port or 5432), PGDATABASE=target.database)
    if target.username:
        env["PGUSER"] = target.username
    if target.password:
        env["PGPASSWORD"] = target.password
    subprocess.run([executable, "--no-password", *args], env=env, check=True)


def sqlite_copy(source, target):
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as incoming:
        with closing(sqlite3.connect(target)) as outgoing:
            incoming.backup(outgoing)
            if outgoing.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("The SQLite copy did not pass its integrity check.")


def backup(url, directory, now=None):
    check_disposable(url)
    target = make_url(url)
    sqlite = target.get_backend_name() == "sqlite"
    extension = ".sqlite3" if sqlite else ".dump"
    profile = target.get_backend_name()
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(KARACHI)
    filename = PREFIX + profile + "-" + now.strftime("%Y%m%d-%H%M%S") + extension
    result = directory / filename
    if result.exists():
        return result
    temporary = directory / (filename + "." + uuid4().hex + ".partial")
    try:
        if sqlite:
            sqlite_copy(Path(target.database), temporary)
        else:
            pg_command(target, "pg_dump", ["--format=custom", "--no-owner", "--no-acl", "--file", str(temporary)])
        os.replace(temporary, result)
    finally:
        temporary.unlink(missing_ok=True)
    pattern = re.compile(re.escape(PREFIX + profile + "-") + r"[0-9]{8}-[0-9]{6}" + re.escape(extension))
    copies = sorted(path for path in directory.iterdir() if path.is_file() and pattern.fullmatch(path.name))
    for old in copies[:-KEEP]:
        old.unlink()
    return result


def restore(url, source):
    check_disposable(url)
    target = make_url(url)
    source = Path(source).resolve(strict=True)
    if target.get_backend_name() == "sqlite":
        destination = Path(target.database).resolve()
        if destination.exists():
            raise ValueError("Restore into a new SQLite path.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix("." + uuid4().hex + ".partial")
        try:
            sqlite_copy(source, temporary)
            if destination.exists():
                raise ValueError("The restore target was created by another process.")
            os.link(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return
    engine = database(url)
    try:
        if inspect(engine).get_table_names():
            raise ValueError("Restore into a fresh, empty PostgreSQL database.")
    finally:
        engine.dispose()
    pg_command(target, "pg_restore", [
        "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl", "--dbname", target.database, str(source),
    ])


def start_daily_backup(url, directory):
    stopping = Event()

    def maintain():
        latest = None
        while not stopping.is_set():
            now = datetime.now(KARACHI)
            if now.hour >= 19 and now.date() != latest:
                try:
                    day = now.strftime("%Y%m%d")
                    if not any(Path(directory).glob(f"{PREFIX}{make_url(url).get_backend_name()}-{day}-*")):
                        path = backup(url, directory, now)
                        LOG.info("Daily backup completed at %s.", path)
                    latest = now.date()
                except Exception:
                    LOG.exception("The daily backup could not be completed.")
            stopping.wait(60)

    Thread(target=maintain, name="daily-database-backup", daemon=True).start()
    return stopping

