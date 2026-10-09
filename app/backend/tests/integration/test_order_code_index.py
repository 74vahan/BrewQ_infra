"""uq_orders_day_code: one code per Yerevan day, enforced by MySQL, and usable for MAX(code)."""

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories.orders import DAY_EXPRESSION_SQL, MAX_CODE_FOR_DAY_SQL, max_code_for_day
from tests.integration.helpers import (
    DUPLICATE_ENTRY,
    db_dt,
    expect_db_error,
    insert_customer,
    insert_order,
    utc,
)

INSERT_ORDER = (
    "INSERT INTO orders (code, customer_id, status, total_amd, created_at, updated_at) "
    "VALUES (:code, :customer_id, 'NEW', 1300, :at, :at)"
)


def _duplicate(conn, customer_id, code, at):
    expect_db_error(
        conn,
        INSERT_ORDER,
        {"code": code, "customer_id": customer_id, "at": db_dt(at)},
        DUPLICATE_ENTRY,
        "uq_orders_day_code",
    )


def test_duplicate_code_on_the_same_yerevan_day_fails(conn):
    customer_id = insert_customer(conn)
    insert_order(conn, customer_id, "A-001", utc(2026, 10, 9, 8, 0))
    _duplicate(conn, customer_id, "A-001", utc(2026, 10, 9, 12, 30))


def test_duplicate_is_global_across_customers(conn):
    first = insert_customer(conn, "11111111-1111-4111-8111-111111111111")
    second = insert_customer(conn, "22222222-2222-4222-8222-222222222222")
    insert_order(conn, first, "A-005", utc(2026, 10, 9, 8, 0))
    _duplicate(conn, second, "A-005", utc(2026, 10, 9, 9, 0))


def test_cancelled_orders_keep_their_code(conn):
    customer_id = insert_customer(conn)
    insert_order(conn, customer_id, "A-001", utc(2026, 10, 9, 8, 0), status="CANCELLED")
    _duplicate(conn, customer_id, "A-001", utc(2026, 10, 9, 9, 0))


def test_different_codes_on_the_same_day_are_fine(conn):
    customer_id = insert_customer(conn)
    for n in range(1, 6):
        insert_order(conn, customer_id, f"A-{n:03d}", utc(2026, 10, 9, 8, n))


def test_same_code_passes_across_the_yerevan_midnight(conn):
    """23:59 and 00:01 in Yerevan are 19:59 and 20:01 UTC: two different business days."""
    customer_id = insert_customer(conn)
    insert_order(conn, customer_id, "A-001", utc(2026, 10, 9, 19, 59))
    insert_order(conn, customer_id, "A-001", utc(2026, 10, 9, 20, 1))
    # ...and each of the two days still rejects its own duplicate.
    _duplicate(conn, customer_id, "A-001", utc(2026, 10, 9, 19, 59, 30))
    _duplicate(conn, customer_id, "A-001", utc(2026, 10, 9, 22, 0))


def test_microsecond_precision_at_the_boundary(conn):
    customer_id = insert_customer(conn)
    insert_order(conn, customer_id, "A-001", utc(2026, 10, 9, 19, 59, 59, 999999))
    insert_order(conn, customer_id, "A-001", utc(2026, 10, 9, 20, 0, 0, 0))
    _duplicate(conn, customer_id, "A-001", utc(2026, 10, 9, 20, 0, 0, 1))


def test_max_code_for_day(conn, engine):
    customer_id = insert_customer(conn)
    for n in (1, 2, 3, 10, 9):
        insert_order(conn, customer_id, f"A-{n:03d}", utc(2026, 10, 9, 8, n))
    insert_order(conn, customer_id, "A-777", utc(2026, 10, 9, 20, 5))  # next Yerevan day
    insert_order(conn, customer_id, "A-555", utc(2026, 10, 9, 19, 59))  # still day one
    conn.commit()

    with Session(engine) as session:
        assert max_code_for_day(session, date(2026, 10, 9)) == "A-555"
        assert max_code_for_day(session, date(2026, 10, 10)) == "A-777"
        assert max_code_for_day(session, date(2026, 10, 11)) is None


def test_string_max_is_numeric_max_for_padded_codes(conn, engine):
    customer_id = insert_customer(conn)
    for n in (9, 99, 100, 998, 999, 10):
        insert_order(conn, customer_id, f"A-{n:03d}", utc(2026, 10, 9, 8, 0, n % 60, n))
    conn.commit()
    with Session(engine) as session:
        assert max_code_for_day(session, date(2026, 10, 9)) == "A-999"


def test_explain_of_max_code_uses_the_functional_index(conn):
    customer_id = insert_customer(conn)
    start = date(2026, 9, 1)
    rows = []
    for day_offset in range(30):
        day = start + timedelta(days=day_offset)
        for n in range(1, 41):
            at = utc(day.year, day.month, day.day, 8, 0) + timedelta(minutes=n)
            rows.append({"code": f"A-{n:03d}", "customer_id": customer_id, "at": db_dt(at)})
    conn.execute(text(INSERT_ORDER), rows)
    conn.commit()
    conn.execute(text("ANALYZE TABLE orders"))

    plan = conn.execute(text("EXPLAIN " + MAX_CODE_FOR_DAY_SQL), {"day": date(2026, 9, 15)})
    row = plan.mappings().one()
    assert row["key"] == "uq_orders_day_code", dict(row)
    assert row["type"] in {"ref", "range"}, dict(row)

    # The barista's "today" list filters by the same expression and uses the same index.
    plan = conn.execute(
        text(f"EXPLAIN SELECT * FROM orders WHERE {DAY_EXPRESSION_SQL}"), {"day": date(2026, 9, 15)}
    )
    row = plan.mappings().one()
    assert row["key"] == "uq_orders_day_code", dict(row)
