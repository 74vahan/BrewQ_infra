"""The real application: health endpoints, error envelope, media, and app.boot."""

import os
import subprocess
import sys

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.core.config import Settings
from app.main import create_app
from app.services.menu_seed import load_seed
from tests.integration.conftest import BACKEND_ROOT, TEST_DATABASE_URL

UNREACHABLE_DB = "mysql+pymysql://nobody:nothing@127.0.0.1:1/none"


def test_health_is_alive_without_touching_the_database():
    # An app pointed at an unreachable database is still alive.
    settings = Settings(_env_file=None, database_url=UNREACHABLE_DB)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_checks_the_database(client):
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_envelope_when_the_database_is_down():
    settings = Settings(_env_file=None, database_url=UNREACHABLE_DB)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Database is unavailable",
            "details": {},
        }
    }


def test_unknown_api_route_is_a_404_envelope(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND",
        "message": "Resource not found",
        "details": {},
    }


def test_wrong_method_is_a_405_envelope(client):
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_openapi_docs_are_off_by_default(client):
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404


def test_openapi_docs_can_be_enabled():
    settings = Settings(_env_file=None, database_url=TEST_DATABASE_URL, enable_docs=True)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/openapi.json").status_code == 200


def test_media_is_not_served_by_default(client):
    assert client.get("/media/menu/latte.svg").status_code == 404


def test_media_is_served_when_enabled():
    settings = Settings(_env_file=None, database_url=TEST_DATABASE_URL, serve_media=True)
    with TestClient(create_app(settings)) as client:
        for item in load_seed().items:
            response = client.get(item.image_url)
            assert response.status_code == 200, item.image_url
            assert response.headers["content-type"].startswith("image/svg+xml")
        assert client.get("/media/menu/missing.svg").status_code == 404


def _run_boot(**flags: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL, **flags}
    return subprocess.run(
        [sys.executable, "-m", "app.boot"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_boot_without_flags_does_nothing(engine):
    done = _run_boot(MIGRATE_ON_START="false", SEED_ON_START="false")
    assert done.returncode == 0, done.stderr
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM menu_items")).scalar() == 0


def test_boot_migrates_and_seeds_a_fresh_database(engine):
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in inspect(connection).get_table_names():
            connection.execute(text(f"DROP TABLE `{table}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    done = _run_boot(MIGRATE_ON_START="true", SEED_ON_START="true")
    assert done.returncode == 0, done.stderr
    again = _run_boot(MIGRATE_ON_START="true", SEED_ON_START="true")
    assert again.returncode == 0, again.stderr

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM menu_items")).scalar() == len(
            load_seed().items
        )
        assert connection.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() == 1
