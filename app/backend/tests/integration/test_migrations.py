"""Alembic: upgrade to head, idempotent re-run, no model/schema drift."""

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from tests.integration.conftest import alembic_config, reset_schema

EXPECTED_TABLES = {
    "alembic_version",
    "cart_items",
    "customers",
    "menu_items",
    "order_events",
    "order_items",
    "orders",
}


def _head() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def _current(engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_upgrade_head_creates_six_tables_plus_alembic_version(engine):
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    assert _current(engine) == _head()


def test_second_upgrade_is_a_noop(engine):
    before = _current(engine)
    command.upgrade(alembic_config(), "head")
    assert _current(engine) == before == _head()
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_alembic_check_reports_no_drift(engine):
    # Raises CommandError if autogenerate would produce any operation.
    command.check(alembic_config())


def test_history_is_linear(engine):
    script = ScriptDirectory.from_config(alembic_config())
    assert len(script.get_heads()) == 1


def test_functional_unique_index_exists(engine):
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT non_unique AS non_unique, seq_in_index AS seq, column_name AS column_name, "
                "expression AS expression "
                "FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'orders' "
                "AND index_name = 'uq_orders_day_code' ORDER BY seq_in_index"
            )
        ).all()
    assert len(rows) == 2
    assert all(row.non_unique == 0 for row in rows)
    assert rows[0].expression is not None and "interval 4 hour" in rows[0].expression.lower()
    assert rows[1].column_name == "code"


def test_tables_use_innodb_and_utf8mb4(engine):
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name AS table_name, engine AS engine, "
                "table_collation AS table_collation "
                "FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name <> 'alembic_version'"
            )
        ).all()
    assert len(rows) == 6
    for row in rows:
        assert row.engine == "InnoDB", row
        assert row.table_collation == "utf8mb4_0900_ai_ci", row


def test_downgrade_and_upgrade_round_trip(engine):
    # Runs last in this module on purpose: it recreates the schema from scratch.
    command.downgrade(alembic_config(), "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    reset_schema(engine)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_enum_like_columns_are_ascii_binary(engine):
    expected = {
        ("menu_items", "category"),
        ("cart_items", "size"),
        ("order_items", "size"),
        ("orders", "status"),
        ("orders", "code"),
        ("order_events", "from_status"),
        ("order_events", "to_status"),
    }
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name AS tbl, column_name AS col, character_set_name AS charset, "
                "collation_name AS collation FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND collation_name IS NOT NULL"
            )
        ).all()
    binary = {
        (row.tbl, row.col) for row in rows if (row.charset, row.collation) == ("ascii", "ascii_bin")
    }
    assert expected <= binary
