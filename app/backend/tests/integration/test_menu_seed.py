"""`python -m app.seed`: idempotent upsert that never overwrites is_available."""

import os
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.menu_seed import apply_seed, load_seed
from tests.integration.conftest import BACKEND_ROOT, TEST_DATABASE_URL
from tests.integration.helpers import insert_menu_item


def _snapshot(engine) -> list[tuple]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, name, category, price_s, price_m, price_l, is_available, image_url "
                "FROM menu_items ORDER BY id"
            )
        ).all()
    return [tuple(row) for row in rows]


def test_seed_twice_gives_identical_state(engine):
    seed = load_seed()
    with Session(engine) as session:
        first = apply_seed(session, seed)
    after_first = _snapshot(engine)
    with Session(engine) as session:
        second = apply_seed(session, seed)
    after_second = _snapshot(engine)

    assert first.created == len(seed.items) and first.updated == 0
    assert (second.created, second.updated, second.unchanged) == (0, 0, len(seed.items))
    assert after_first == after_second
    assert len(after_second) == len(seed.items)
    assert all(row[6] == 1 for row in after_second)  # is_available defaults to TRUE


def test_seed_never_overwrites_is_available_but_restores_other_fields(engine):
    seed = load_seed()
    with Session(engine) as session:
        apply_seed(session, seed)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE menu_items SET is_available = FALSE, price_m = 1, image_url = NULL "
                "WHERE name = 'Latte'"
            )
        )
    with Session(engine) as session:
        result = apply_seed(session, seed)

    latte_seed = next(item for item in seed.items if item.name == "Latte")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT is_available, price_m, image_url FROM menu_items WHERE name = 'Latte'")
        ).one()
    assert result.updated == 1
    assert row.is_available == 0  # barista's stop-list decision survives
    assert row.price_m == latte_seed.price_m
    assert row.image_url == latte_seed.image_url


def test_seed_matches_names_case_insensitively_and_deletes_nothing(engine):
    with engine.begin() as connection:
        insert_menu_item(connection, name="latte", category="tea", price_m=5)
        insert_menu_item(connection, name="Retired Special", category="cake", price_m=999)
    seed = load_seed()
    with Session(engine) as session:
        result = apply_seed(session, seed)

    assert result.orphaned == ("Retired Special",)
    assert result.created == len(seed.items) - 1  # "latte" matched the seed's "Latte"
    with engine.connect() as connection:
        names = {row[0] for row in connection.execute(text("SELECT name FROM menu_items"))}
        category = connection.execute(
            text("SELECT category FROM menu_items WHERE name = 'Latte'")
        ).scalar()
    assert "Retired Special" in names
    assert category == "coffee"


def test_python_m_app_seed_twice(engine):
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    for _ in range(2):
        done = subprocess.run(
            [sys.executable, "-m", "app.seed"],
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stderr
    expected = len(load_seed().items)
    assert len(_snapshot(engine)) == expected
    assert "created=0 updated=0 unchanged=" in done.stderr + done.stdout
