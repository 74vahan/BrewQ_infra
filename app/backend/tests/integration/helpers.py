"""Raw-SQL helpers: tests insert rows directly to exercise the schema, not the app."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

CHECK_VIOLATED = 3819
DUPLICATE_ENTRY = 1062
FK_CHILD_FAILS = 1452
FK_PARENT_FAILS = 1451
OUT_OF_RANGE = 1264


def utc(*args: int) -> datetime:
    """Aware UTC datetime."""
    return datetime(*args, tzinfo=UTC)


def db_dt(value: datetime) -> datetime:
    """Naive UTC value for raw SQL parameters (the column stores UTC)."""
    return value.astimezone(UTC).replace(tzinfo=None)


def insert_menu_item(conn: Connection, **overrides: Any) -> int:
    values = {
        "name": "Latte",
        "category": "coffee",
        "price_s": 1100,
        "price_m": 1300,
        "price_l": 1500,
        "image_url": None,
        **overrides,
    }
    result = conn.execute(
        text(
            "INSERT INTO menu_items (name, category, price_s, price_m, price_l, image_url) "
            "VALUES (:name, :category, :price_s, :price_m, :price_l, :image_url)"
        ),
        values,
    )
    return result.lastrowid


def insert_customer(conn: Connection, device_id: str | None = None, **overrides: Any) -> int:
    values = {
        "device_id": device_id or "11111111-1111-4111-8111-111111111111",
        "name": None,
        "created_at": db_dt(utc(2026, 10, 9, 8, 0)),
        **overrides,
    }
    result = conn.execute(
        text(
            "INSERT INTO customers (device_id, name, created_at) "
            "VALUES (:device_id, :name, :created_at)"
        ),
        values,
    )
    return result.lastrowid


def insert_order(
    conn: Connection,
    customer_id: int,
    code: str = "A-001",
    created_at: datetime | None = None,
    **overrides: Any,
) -> int:
    created = db_dt(created_at or utc(2026, 10, 9, 8, 0))
    values = {
        "code": code,
        "customer_id": customer_id,
        "status": "NEW",
        "total_amd": 1300,
        "created_at": created,
        "updated_at": created,
        **overrides,
    }
    result = conn.execute(
        text(
            "INSERT INTO orders (code, customer_id, status, total_amd, created_at, updated_at) "
            "VALUES (:code, :customer_id, :status, :total_amd, :created_at, :updated_at)"
        ),
        values,
    )
    return result.lastrowid


def expect_db_error(conn: Connection, sql: str, params: dict[str, Any], errno: int, name: str):
    """Run a statement that must fail with MySQL `errno`, mentioning constraint `name`."""
    # A savepoint keeps the rows inserted earlier in the same test intact.
    with pytest.raises(DBAPIError) as info, conn.begin_nested():
        conn.execute(text(sql), params)
    code, message = info.value.orig.args[0], str(info.value.orig)
    assert code == errno, f"expected errno {errno}, got {code}: {message}"
    assert name in message, f"constraint {name!r} not mentioned in: {message}"
