"""Apply the versioned local schema."""

from alembic import command
from alembic.config import Config

from backend.data.database import ROOT, check_disposable


def migrate(engine, revision="head"):
    check_disposable(engine.url)
    config = Config()
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.attributes["engine"] = engine
    command.upgrade(config, revision)

