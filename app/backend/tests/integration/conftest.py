"""Integration fixtures: a real MySQL 8.4 database, reset and migrated once per session.

The database comes from TEST_DATABASE_URL (or DATABASE_URL). Its name MUST end with
"_test": the session fixture drops every table in it, and refusing anything else
protects a development database from being wiped by accident.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.api.deps import get_clock
from app.core.clock import FakeClock
from app.core.config import Settings, get_settings
from app.main import create_app
from tests.integration.api_helpers import BARISTA_PASSWORD, BARISTA_TOKEN_SECRET

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Children first, so DELETE respects RESTRICT foreign keys.
TABLES_CHILD_FIRST = [
    "order_events",
    "order_items",
    "orders",
    "cart_items",
    "customers",
    "menu_items",
]


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.exit(
            "Integration tests need a MySQL database: set TEST_DATABASE_URL (or DATABASE_URL).",
            returncode=2,
        )
    return url


# Alembic's env.py reads DATABASE_URL through get_settings(); point it at the test DB.
TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
get_settings.cache_clear()


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["configure_logger"] = False
    return config


def reset_schema(engine: Engine) -> None:
    """Drop every table (including alembic_version) and migrate to head."""
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in inspect(connection).get_table_names():
            connection.execute(text(f"DROP TABLE `{table}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    command.upgrade(alembic_config(), "head")


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        barista_password=SecretStr(BARISTA_PASSWORD),
        barista_token_secret=SecretStr(BARISTA_TOKEN_SECRET),
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    database = make_url(TEST_DATABASE_URL).database or ""
    if not database.endswith("_test"):
        pytest.exit(
            f"Refusing to reset database {database!r}: its name must end with '_test'. "
            "Create such a database and point TEST_DATABASE_URL at it.",
            returncode=2,
        )
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        reset_schema(engine)
    except OperationalError as exc:
        pytest.exit(f"MySQL is not reachable at the test URL: {exc.orig}", returncode=2)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> Iterator[None]:
    """Every test starts and ends with empty tables."""
    _wipe(engine)
    yield
    _wipe(engine)


def _wipe(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in TABLES_CHILD_FIRST:
            connection.execute(text(f"DELETE FROM `{table}`"))


@pytest.fixture
def conn(engine: Engine) -> Iterator:
    """A connection in autocommit-per-statement style for raw SQL tests."""
    with engine.connect() as connection:
        yield connection


@pytest.fixture
def clock() -> FakeClock:
    """Application time: midday in Yerevan, far from any day boundary."""
    return FakeClock(datetime(2026, 10, 9, 8, 0, tzinfo=UTC))


@pytest.fixture
def app(test_settings: Settings, clock: FakeClock) -> FastAPI:
    application = create_app(test_settings)
    application.dependency_overrides[get_clock] = lambda: clock
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
