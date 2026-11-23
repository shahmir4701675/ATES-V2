"""Connection setup used by the application and migration runner."""

from pathlib import Path

from sqlalchemy import create_engine, event, make_url

ROOT = Path(__file__).resolve().parents[2]


def database(url):
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def sqlite_settings(connection, _):
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
    elif engine.dialect.name == "postgresql":
        @event.listens_for(engine, "connect")
        def postgres_settings(connection, _):
            with connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
            connection.commit()
    return engine


def check_disposable(url):
    """Restrict automatic setup and test writes to explicitly isolated local targets."""
    target = make_url(url)
    if target.get_backend_name() == "sqlite" and target.database and not target.query:
        path = Path(target.database).resolve()
        if path.is_relative_to((ROOT / ".ates").resolve()):
            return
    if (target.get_backend_name() == "postgresql"
        and target.host in {"localhost", "127.0.0.1", "::1"}
        and not target.query
        and (target.database or "").startswith("ates_disposable_")):
        return
    raise ValueError("Setup requires a SQLite file under .ates or an ates_disposable_ PostgreSQL database on loopback.")

