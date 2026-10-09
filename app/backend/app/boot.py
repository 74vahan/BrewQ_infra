"""`python -m app.boot` - container start-up: migrate and seed according to env flags."""

import logging
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_db_engine
from app.seed import run_seed

log = logging.getLogger("app.boot")

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
DB_WAIT_SECONDS = 60


def wait_for_db(engine: Engine, timeout: float = DB_WAIT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            if time.monotonic() >= deadline:
                raise
            log.info("Waiting for the database: %s", exc.orig)
            time.sleep(2)


def run_migrations() -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logger"] = False  # keep the application's logging
    command.upgrade(config, "head")


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.migrate_on_start or settings.seed_on_start:
        engine = create_db_engine(settings)
        try:
            wait_for_db(engine)
        finally:
            engine.dispose()
    if settings.migrate_on_start:
        log.info("Running migrations")
        run_migrations()
    if settings.seed_on_start:
        log.info("Seeding the menu")
        run_seed()
    return 0


if __name__ == "__main__":
    sys.exit(main())
