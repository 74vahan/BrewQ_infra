"""POST /api/orders: the checkout transaction, its errors, codes and the Yerevan midnight."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import (
    DEVICE_A,
    DEVICE_B,
    TIMESTAMP_RE,
    add_to_cart,
    device,
    error_of,
    make_device_id,
    place_order,
    seed_menu,
)
from tests.integration.helpers import db_dt, insert_customer, utc


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


def _count(engine, table: str) -> int:
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def test_checkout_creates_a_new_order_and_clears_the_cart(client, ids, engine, clock):
    add_to_cart(client, ids["latte"], "M", 2)
    add_to_cart(client, ids["espresso"], "L", 1)
    response = client.post("/api/orders", headers=device())
    assert response.status_code == 201
    order = response.json()
    assert set(order) == {
        "id",
        "code",
        "status",
        "total_amd",
        "created_at",
        "updated_at",
        "can_cancel",
        "items",
    }
    assert order["code"] == "A-001"
    assert order["status"] == "NEW"
    assert order["total_amd"] == 2 * 1300 + 1100
    assert order["can_cancel"] is True
    assert TIMESTAMP_RE.match(order["created_at"])
    assert order["created_at"] == order["updated_at"] == "2026-10-09T08:00:00.000000Z"
    assert order["items"] == [
        {
            "menu_item_id": ids["latte"],
            "name": "Latte",
            "size": "M",
            "qty": 2,
            "unit_price_amd": 1300,
            "line_total_amd": 2600,
        },
        {
            "menu_item_id": ids["espresso"],
            "name": "Espresso",
            "size": "L",
            "qty": 1,
            "unit_price_amd": 1100,
            "line_total_amd": 1100,
        },
    ]
    assert client.get("/api/cart", headers=device()).json()["items"] == []
    assert _count(engine, "cart_items") == 0


def test_checkout_writes_the_creation_event_in_the_same_transaction(client, ids, engine):
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    with engine.connect() as connection:
        events = connection.execute(
            text("SELECT order_id, from_status, to_status, created_at FROM order_events")
        ).all()
    assert len(events) == 1
    assert events[0].order_id == order["id"]
    assert events[0].from_status is None
    assert events[0].to_status == "NEW"
    assert events[0].created_at == datetime(2026, 10, 9, 8, 0)


def test_order_lines_keep_the_price_at_the_time_of_ordering(client, ids, engine):
    add_to_cart(client, ids["latte"], "M", 2)
    order = place_order(client)
    with engine.begin() as connection:
        connection.execute(text("UPDATE menu_items SET price_m = 9999 WHERE name = 'Latte'"))
    fetched = client.get(f"/api/orders/{order['id']}", headers=device()).json()
    assert fetched["items"][0]["unit_price_amd"] == 1300
    assert fetched["total_amd"] == 2600


def test_empty_cart_is_409(client, ids, engine):
    response = client.post("/api/orders", headers=device())
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "CART_EMPTY"
    assert error["details"] == {}
    assert _count(engine, "orders") == 0


def test_body_is_optional_and_an_empty_object_is_allowed(client, ids):
    add_to_cart(client, ids["latte"], "M")
    response = client.post("/api/orders", json={}, headers=device())
    assert response.status_code == 201


def test_unavailable_lines_are_all_reported_and_nothing_changes(client, ids, engine):
    add_to_cart(client, ids["latte"], "L")
    add_to_cart(client, ids["cheesecake"], "M")
    add_to_cart(client, ids["espresso"], "M")
    with engine.begin() as connection:
        connection.execute(text("UPDATE menu_items SET is_available = FALSE WHERE name = 'Latte'"))
    cart_before = client.get("/api/cart", headers=device()).json()
    response = client.post("/api/orders", headers=device())
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "CART_HAS_UNAVAILABLE_ITEMS"
    latte_line = cart_before["items"][0]
    assert error["details"] == {
        "items": [
            {
                "cart_item_id": latte_line["id"],
                "menu_item_id": ids["latte"],
                "name": "Latte",
                "size": "L",
                "reason": "unavailable",
            }
        ]
    }
    assert _count(engine, "orders") == 0
    assert client.get("/api/cart", headers=device()).json() == cart_before


def test_size_not_offered_reason_when_a_price_disappears(client, ids, engine):
    add_to_cart(client, ids["espresso"], "L")
    add_to_cart(client, ids["latte"], "S")
    with engine.begin() as connection:
        connection.execute(text("UPDATE menu_items SET price_l = NULL WHERE name = 'Espresso'"))
        connection.execute(text("UPDATE menu_items SET is_available = FALSE WHERE name = 'Latte'"))
    error = error_of(client.post("/api/orders", headers=device()))
    assert error["code"] == "CART_HAS_UNAVAILABLE_ITEMS"
    reasons = {item["name"]: item["reason"] for item in error["details"]["items"]}
    assert reasons == {"Espresso": "size_not_offered", "Latte": "unavailable"}


def test_active_order_blocks_a_second_checkout(client, ids, engine):
    add_to_cart(client, ids["latte"], "M")
    first = place_order(client)
    add_to_cart(client, ids["cheesecake"], "M")
    response = client.post("/api/orders", headers=device())
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "ACTIVE_ORDER_EXISTS"
    assert error["details"] == {"order_id": first["id"], "code": "A-001", "status": "NEW"}
    assert _count(engine, "orders") == 1
    assert len(client.get("/api/cart", headers=device()).json()["items"]) == 1  # cart kept


@pytest.mark.parametrize("status", ["IN_PROGRESS", "READY"])
def test_active_order_error_reports_the_current_status(client, ids, engine, status):
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = :s WHERE id = :id"), {"s": status, "id": order["id"]}
        )
    add_to_cart(client, ids["latte"], "M")
    error = error_of(client.post("/api/orders", headers=device()))
    assert error["code"] == "ACTIVE_ORDER_EXISTS"
    assert error["details"]["status"] == status


@pytest.mark.parametrize("status", ["PICKED_UP", "CANCELLED"])
def test_a_finished_order_does_not_block_a_new_one(client, ids, engine, status):
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = :s WHERE id = :id"), {"s": status, "id": order["id"]}
        )
    add_to_cart(client, ids["latte"], "M")
    second = place_order(client)
    assert second["code"] == "A-002"
    assert second["id"] != order["id"]


def test_codes_run_consecutively_across_customers(client, ids):
    codes = []
    for device_id in (DEVICE_A, DEVICE_B):
        add_to_cart(client, ids["latte"], "M", device_id=device_id)
        codes.append(place_order(client, device_id)["code"])
    assert codes == ["A-001", "A-002"]


def test_cancelled_order_codes_are_not_reused(client, ids, engine):
    add_to_cart(client, ids["latte"], "M")
    first = place_order(client)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = 'CANCELLED' WHERE id = :id"), {"id": first["id"]}
        )
    add_to_cart(client, ids["latte"], "M")
    assert place_order(client)["code"] == "A-002"


def test_a_failed_checkout_of_one_customer_does_not_touch_another(client, ids, engine):
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_A)
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_B)
    client.post("/api/orders", headers=device(DEVICE_A))
    assert client.post("/api/orders", headers=device(DEVICE_A)).status_code == 409
    assert place_order(client, DEVICE_B)["code"] == "A-002"


# --- Yerevan day -------------------------------------------------------------------------------


def make_extra_customer(client, ids, number: int) -> str:
    device_id = make_device_id(number)
    add_to_cart(client, ids["latte"], "M", device_id=device_id)
    return place_order(client, device_id)["code"]


def test_code_counter_resets_at_the_yerevan_midnight(client, ids, clock):
    # 23:59:59 in Yerevan is 19:59:59 UTC
    clock.set(utc(2026, 10, 9, 19, 59, 59))
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_A)
    before = place_order(client, DEVICE_A)
    assert before["code"] == "A-001"
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_B)
    assert place_order(client, DEVICE_B)["code"] == "A-002"

    # 00:00:01 on the next Yerevan day is 20:00:01 UTC
    clock.set(utc(2026, 10, 9, 20, 0, 1))
    third = make_extra_customer(client, ids, 3)
    assert third == "A-001"
    assert make_extra_customer(client, ids, 4) == "A-002"


def test_midnight_counts_the_same_customer_again_the_next_day(client, ids, engine, clock):
    clock.set(utc(2026, 10, 9, 19, 59, 59))
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = 'PICKED_UP' WHERE id = :id"), {"id": order["id"]}
        )
    clock.set(utc(2026, 10, 9, 20, 0, 1))
    add_to_cart(client, ids["latte"], "M")
    assert place_order(client)["code"] == "A-001"


def test_the_order_timestamps_come_from_the_clock(client, ids, clock):
    clock.set(datetime(2026, 10, 9, 19, 59, 59, 123456, tzinfo=UTC))
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    assert order["created_at"] == "2026-10-09T19:59:59.123456Z"


def test_the_day_of_the_code_is_the_day_of_created_at(client, ids, engine, clock):
    """A-001 at 19:59:59.999999 UTC and again at 20:00:00 UTC (next Yerevan day)."""
    clock.set(datetime(2026, 10, 9, 19, 59, 59, 999999, tzinfo=UTC))
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_A)
    first = place_order(client, DEVICE_A)
    clock.set(datetime(2026, 10, 9, 20, 0, 0, tzinfo=UTC))
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_B)
    second = place_order(client, DEVICE_B)
    assert (first["code"], second["code"]) == ("A-001", "A-001")


# --- the daily limit --------------------------------------------------------------------------


def _fill_day_up_to(engine, last_number: int) -> None:
    """Directly insert finished orders A-001..A-<last_number> for today (Yerevan)."""
    created = db_dt(utc(2026, 10, 9, 7, 0)).isoformat(sep=" ")
    with engine.begin() as connection:
        customer_id = insert_customer(connection, "99999999-9999-4999-8999-999999999999")
        # One multi-row INSERT: a thousand single-row statements are needlessly slow.
        values = ", ".join(
            f"('A-{number:03d}', {customer_id}, 'PICKED_UP', 1300, '{created}', '{created}')"
            for number in range(1, last_number + 1)
        )
        connection.execute(
            text(
                "INSERT INTO orders (code, customer_id, status, total_amd, created_at, updated_at) "
                f"VALUES {values}"
            )
        )


def test_a_999_is_the_last_code_of_the_day(client, ids, engine):
    _fill_day_up_to(engine, 998)
    add_to_cart(client, ids["latte"], "M")
    assert place_order(client)["code"] == "A-999"


def test_daily_limit_reached_keeps_the_cart_intact(client, ids, engine):
    _fill_day_up_to(engine, 999)
    add_to_cart(client, ids["latte"], "M", 2)
    add_to_cart(client, ids["cheesecake"], "M")
    cart_before = client.get("/api/cart", headers=device()).json()
    orders_before = _count(engine, "orders")

    response = client.post("/api/orders", headers=device())
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "DAILY_ORDER_LIMIT_REACHED"
    assert error["details"] == {"limit": 999}
    assert _count(engine, "orders") == orders_before
    assert client.get("/api/cart", headers=device()).json() == cart_before


def test_daily_limit_does_not_block_the_next_yerevan_day(client, ids, engine, clock):
    _fill_day_up_to(engine, 999)
    clock.set(utc(2026, 10, 9, 20, 0, 0))
    add_to_cart(client, ids["latte"], "M")
    assert place_order(client)["code"] == "A-001"
