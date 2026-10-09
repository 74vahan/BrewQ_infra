"""Every CHECK, UNIQUE and FOREIGN KEY of memory/02-database.md really fires in MySQL."""

import pytest
from sqlalchemy import text

from tests.integration.helpers import (
    CHECK_VIOLATED,
    DUPLICATE_ENTRY,
    FK_CHILD_FAILS,
    FK_PARENT_FAILS,
    OUT_OF_RANGE,
    db_dt,
    expect_db_error,
    insert_customer,
    insert_menu_item,
    insert_order,
    utc,
)

NOW = db_dt(utc(2026, 10, 9, 8, 0))

INSERT_MENU = (
    "INSERT INTO menu_items (name, category, price_s, price_m, price_l) "
    "VALUES ('X', :category, :price_s, :price_m, :price_l)"
)
INSERT_CART = (
    "INSERT INTO cart_items (customer_id, menu_item_id, size, qty, updated_at) "
    "VALUES (:customer_id, :menu_item_id, :size, :qty, :now)"
)
INSERT_ORDER = (
    "INSERT INTO orders (code, customer_id, status, total_amd, created_at, updated_at) "
    "VALUES (:code, :customer_id, :status, 1300, :now, :now)"
)
INSERT_ORDER_ITEM = (
    "INSERT INTO order_items (order_id, menu_item_id, size, qty, unit_price_amd) "
    "VALUES (:order_id, :menu_item_id, :size, :qty, :price)"
)
INSERT_EVENT = (
    "INSERT INTO order_events (order_id, from_status, to_status, created_at) "
    "VALUES (:order_id, :from_status, :to_status, :now)"
)


@pytest.fixture
def ids(conn):
    customer_id = insert_customer(conn)
    menu_item_id = insert_menu_item(conn)
    order_id = insert_order(conn, customer_id)
    return {"customer_id": customer_id, "menu_item_id": menu_item_id, "order_id": order_id}


# --- CHECK constraints -------------------------------------------------------------------

MENU_OK = {"category": "coffee", "price_s": 1, "price_m": 1, "price_l": 1}


@pytest.mark.parametrize(
    ("constraint", "overrides"),
    [
        ("ck_menu_items_category", {"category": "soup"}),
        ("ck_menu_items_category", {"category": "COFFEE_"}),
        ("ck_menu_items_category", {"category": "Coffee"}),
        ("ck_menu_items_prices", {"price_m": 0}),
        ("ck_menu_items_prices", {"price_s": 0}),
        ("ck_menu_items_prices", {"price_l": 0}),
    ],
)
def test_menu_item_checks(conn, constraint, overrides):
    expect_db_error(conn, INSERT_MENU, {**MENU_OK, **overrides}, CHECK_VIOLATED, constraint)


def test_menu_item_valid_variants_pass(conn):
    conn.execute(text(INSERT_MENU), {**MENU_OK, "price_s": None, "price_l": None})


def test_unsigned_price_rejects_negative(conn):
    expect_db_error(conn, INSERT_MENU, {**MENU_OK, "price_m": -1}, OUT_OF_RANGE, "price_m")


@pytest.mark.parametrize(
    ("constraint", "overrides"),
    [
        ("ck_cart_items_size", {"size": "X"}),
        ("ck_cart_items_size", {"size": "s"}),
        ("ck_cart_items_qty", {"qty": 0}),
        ("ck_cart_items_qty", {"qty": 21}),
    ],
)
def test_cart_item_checks(conn, ids, constraint, overrides):
    params = {**ids, "size": "M", "qty": 1, "now": NOW, **overrides}
    expect_db_error(conn, INSERT_CART, params, CHECK_VIOLATED, constraint)


@pytest.mark.parametrize("qty", [1, 20])
def test_cart_item_qty_bounds_are_inclusive(conn, ids, qty):
    conn.execute(text(INSERT_CART), {**ids, "size": "M", "qty": qty, "now": NOW})


@pytest.mark.parametrize(
    ("constraint", "overrides"),
    [
        ("ck_orders_code", {"code": "B-001"}),
        ("ck_orders_code", {"code": "A-000"}),
        ("ck_orders_code", {"code": "A-1"}),
        ("ck_orders_code", {"code": "001"}),
        ("ck_orders_code", {"code": "A-abc"}),
        ("ck_orders_code", {"code": "A-12a"}),
        ("ck_orders_code", {"code": "a-001"}),
        ("ck_orders_status", {"status": "DONE"}),
        ("ck_orders_status", {"status": "new"}),
        ("ck_orders_status", {"status": "In_Progress"}),
    ],
)
def test_order_checks(conn, ids, constraint, overrides):
    params = {"code": "A-001", "status": "NEW", "customer_id": ids["customer_id"], "now": NOW}
    expect_db_error(conn, INSERT_ORDER, {**params, **overrides}, CHECK_VIOLATED, constraint)


def test_order_code_boundaries_pass(conn, ids):
    for code in ("A-002", "A-999"):
        conn.execute(
            text(INSERT_ORDER),
            {"code": code, "status": "NEW", "customer_id": ids["customer_id"], "now": NOW},
        )


@pytest.mark.parametrize(
    ("constraint", "overrides"),
    [
        ("ck_order_items_size", {"size": "X"}),
        ("ck_order_items_size", {"size": "m"}),
        ("ck_order_items_qty", {"qty": 0}),
        ("ck_order_items_qty", {"qty": 21}),
        ("ck_order_items_price", {"price": 0}),
    ],
)
def test_order_item_checks(conn, ids, constraint, overrides):
    params = {
        "order_id": ids["order_id"],
        "menu_item_id": ids["menu_item_id"],
        "size": "M",
        "qty": 1,
        "price": 1300,
        **overrides,
    }
    expect_db_error(conn, INSERT_ORDER_ITEM, params, CHECK_VIOLATED, constraint)


@pytest.mark.parametrize(
    ("constraint", "overrides"),
    [
        ("ck_order_events_from_status", {"from_status": "DONE"}),
        ("ck_order_events_from_status", {"from_status": "new"}),
        ("ck_order_events_to_status", {"to_status": "DONE"}),
        ("ck_order_events_to_status", {"to_status": "in_progress"}),
    ],
)
def test_order_event_checks(conn, ids, constraint, overrides):
    params = {
        "order_id": ids["order_id"],
        "from_status": "NEW",
        "to_status": "IN_PROGRESS",
        "now": NOW,
        **overrides,
    }
    expect_db_error(conn, INSERT_EVENT, params, CHECK_VIOLATED, constraint)


def test_creation_event_has_null_from_status(conn, ids):
    conn.execute(
        text(INSERT_EVENT),
        {"order_id": ids["order_id"], "from_status": None, "to_status": "NEW", "now": NOW},
    )


def test_order_event_to_status_is_required(conn, ids):
    with pytest.raises(Exception, match="to_status"), conn.begin_nested():
        conn.execute(
            text(INSERT_EVENT),
            {"order_id": ids["order_id"], "from_status": None, "to_status": None, "now": NOW},
        )


# --- UNIQUE constraints ------------------------------------------------------------------


def test_menu_item_name_is_unique_case_insensitively(conn):
    insert_menu_item(conn, name="Latte")
    for duplicate in ("Latte", "LATTE", "latte"):
        expect_db_error(
            conn,
            INSERT_MENU.replace("'X'", f"'{duplicate}'"),
            MENU_OK,
            DUPLICATE_ENTRY,
            "uq_menu_items_name",
        )


def test_customer_device_id_is_unique(conn):
    insert_customer(conn)
    expect_db_error(
        conn,
        "INSERT INTO customers (device_id, created_at) VALUES (:d, :now)",
        {"d": "11111111-1111-4111-8111-111111111111", "now": NOW},
        DUPLICATE_ENTRY,
        "uq_customers_device_id",
    )


def test_cart_line_is_unique_per_customer_item_size(conn, ids):
    params = {**ids, "size": "M", "qty": 1, "now": NOW}
    conn.execute(text(INSERT_CART), params)
    expect_db_error(conn, INSERT_CART, params, DUPLICATE_ENTRY, "uq_cart_items_line")
    # A different size of the same item is a different line.
    conn.execute(text(INSERT_CART), {**params, "size": "L"})


def test_order_line_is_unique_per_order_item_size(conn, ids):
    params = {
        "order_id": ids["order_id"],
        "menu_item_id": ids["menu_item_id"],
        "size": "M",
        "qty": 1,
        "price": 1300,
    }
    conn.execute(text(INSERT_ORDER_ITEM), params)
    expect_db_error(conn, INSERT_ORDER_ITEM, params, DUPLICATE_ENTRY, "uq_order_items_line")


# --- FOREIGN KEYS --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "params", "fk"),
    [
        (
            INSERT_CART,
            {"customer_id": 999999, "menu_item_id": 1, "size": "M", "qty": 1, "now": NOW},
            "fk_cart_items_customer",
        ),
        (
            INSERT_ORDER,
            {"code": "A-001", "status": "NEW", "customer_id": 999999, "now": NOW},
            "fk_orders_customer",
        ),
        (
            INSERT_ORDER_ITEM,
            {"order_id": 999999, "menu_item_id": 1, "size": "M", "qty": 1, "price": 1},
            "fk_order_items_order",
        ),
        (
            INSERT_EVENT,
            {"order_id": 999999, "from_status": None, "to_status": "NEW", "now": NOW},
            "fk_order_events_order",
        ),
    ],
)
def test_foreign_keys_reject_missing_parent(conn, sql, params, fk):
    # The referenced menu item must exist so that only the tested FK can fail.
    menu_item_id = insert_menu_item(conn)
    params = {**params, **({"menu_item_id": menu_item_id} if "menu_item_id" in params else {})}
    expect_db_error(conn, sql, params, FK_CHILD_FAILS, fk)


@pytest.mark.parametrize(
    ("sql", "fk"),
    [(INSERT_CART, "fk_cart_items_menu_item"), (INSERT_ORDER_ITEM, "fk_order_items_menu_item")],
)
def test_menu_item_fks_reject_missing_menu_item(conn, ids, sql, fk):
    params = {
        **ids,
        "menu_item_id": 999999,
        "size": "M",
        "qty": 1,
        "price": 1300,
        "now": NOW,
    }
    expect_db_error(conn, sql, params, FK_CHILD_FAILS, fk)


def test_menu_item_with_orders_cannot_be_deleted(conn, ids):
    conn.execute(
        text(INSERT_ORDER_ITEM),
        {
            "order_id": ids["order_id"],
            "menu_item_id": ids["menu_item_id"],
            "size": "M",
            "qty": 1,
            "price": 1300,
        },
    )
    expect_db_error(
        conn,
        "DELETE FROM menu_items WHERE id = :id",
        {"id": ids["menu_item_id"]},
        FK_PARENT_FAILS,
        "fk_order_items_menu_item",
    )


def test_customer_with_orders_cannot_be_deleted(conn, ids):
    expect_db_error(
        conn,
        "DELETE FROM customers WHERE id = :id",
        {"id": ids["customer_id"]},
        FK_PARENT_FAILS,
        "fk_orders_customer",
    )


def test_order_with_events_cannot_be_deleted(conn, ids):
    conn.execute(
        text(INSERT_EVENT),
        {"order_id": ids["order_id"], "from_status": None, "to_status": "NEW", "now": NOW},
    )
    expect_db_error(
        conn,
        "DELETE FROM orders WHERE id = :id",
        {"id": ids["order_id"]},
        FK_PARENT_FAILS,
        "fk_order_events_order",
    )


def test_cart_rows_cascade_with_the_customer(conn):
    customer_id = insert_customer(conn)
    menu_item_id = insert_menu_item(conn)
    conn.execute(
        text(INSERT_CART),
        {
            "customer_id": customer_id,
            "menu_item_id": menu_item_id,
            "size": "M",
            "qty": 1,
            "now": NOW,
        },
    )
    conn.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    assert conn.execute(text("SELECT COUNT(*) FROM cart_items")).scalar() == 0


# --- Defaults, charset, precision ----------------------------------------------------------


def test_server_defaults(conn, ids):
    status = conn.execute(
        text("SELECT status FROM orders WHERE id = :id"), {"id": ids["order_id"]}
    ).scalar()
    assert status == "NEW"
    assert conn.execute(text("SELECT is_available FROM menu_items")).scalar() == 1
    assert conn.execute(text("SELECT name FROM customers")).scalar() is None


def test_utf8mb4_names_round_trip(conn):
    # Armenian, Russian and a 4-byte character, built from code points to keep sources ASCII.
    name = "".join(
        chr(c) for c in (0x531, 0x576, 0x56B, 0x20, 0x418, 0x432, 0x430, 0x43D, 0x20, 0x1F600)
    )
    customer_id = insert_customer(conn, name=name)
    stored = conn.execute(
        text("SELECT name FROM customers WHERE id = :id"), {"id": customer_id}
    ).scalar()
    assert stored == name


def test_datetime_keeps_microseconds(conn):
    moment = utc(2026, 10, 9, 8, 15, 30, 123456)
    customer_id = insert_customer(conn, created_at=db_dt(moment))
    stored = conn.execute(
        text("SELECT created_at FROM customers WHERE id = :id"), {"id": customer_id}
    ).scalar()
    assert stored == db_dt(moment)
