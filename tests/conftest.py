"""All test writes are scoped to synthetic, disposable databases."""

import os
from time import sleep
from uuid import uuid4
import warnings

import pytest

from backend.cli import LOCAL
from backend.data.database import check_disposable, database
from backend.data.migrate import migrate

TEST_SECRET = "test-only-session-key-longer-than-thirty-two-bytes"
TEST_PASSWORD = "gate-only-password"


@pytest.fixture
def local_db():
    root = LOCAL / "tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / (str(uuid4()) + ".sqlite3")
    url = f"sqlite:///{path.as_posix()}"
    engine = database(url)
    try:
        yield engine
    finally:
        engine.dispose()
        for _ in range(10):
            try:
                path.unlink(missing_ok=True)
                break
            except PermissionError:
                sleep(0.25)
        else:
            warnings.warn(f"The local synthetic fixture is still locked and was retained at {path}.", stacklevel=1)


@pytest.fixture
def postgres_db():
    url = os.getenv("ATES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ATES_TEST_DATABASE_URL for the disposable PostgreSQL test.")
    check_disposable(url)
    engine = database(url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def migrated_db(local_db):
    migrate(local_db)
    return local_db

