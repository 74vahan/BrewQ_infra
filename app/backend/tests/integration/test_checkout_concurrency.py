"""Races around checkout: codes stay unique and consecutive, one customer gets one order."""

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import (
    DEVICE_A,
    add_to_cart,
    device,
    error_of,
    make_device_id,
    seed_menu,
)


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


def _parallel(function, count: int) -> list:
    """Run `function(index)` in `count` threads released at the same instant."""
    barrier = Barrier(count)

    def run(index: int):
        barrier.wait()
        return function(index)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(run, range(count)))


def test_ten_parallel_checkouts_get_consecutive_codes_without_duplicates(
    client, ids, engine, caplog
):
    customers = [make_device_id(number) for number in range(1, 11)]
    for device_id in customers:
        add_to_cart(client, ids["latte"], "M", 2, device_id=device_id)

    with caplog.at_level(logging.INFO, logger="app.services.checkout"):
        responses = _parallel(
            lambda index: client.post("/api/orders", headers=device(customers[index])), 10
        )

    assert [response.status_code for response in responses] == [201] * 10, [
        response.text for response in responses if response.status_code != 201
    ]
    codes = sorted(response.json()["code"] for response in responses)
    assert codes == [f"A-{number:03d}" for number in range(1, 11)]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM orders")).scalar() == 10
        assert connection.execute(text("SELECT COUNT(DISTINCT code) FROM orders")).scalar() == 10
        assert connection.execute(text("SELECT COUNT(*) FROM order_events")).scalar() == 10
        assert connection.execute(text("SELECT COUNT(*) FROM order_items")).scalar() == 10
        assert connection.execute(text("SELECT COUNT(*) FROM cart_items")).scalar() == 0
    # the race really happened: the unique index made some of them repeat
    assert any("lost a race" in record.getMessage() for record in caplog.records)


def test_repeated_parallel_rounds_stay_consistent(client, ids, engine):
    """Two more rounds of 6, finishing the previous orders in between."""
    customers = [make_device_id(number) for number in range(1, 7)]
    expected = 0
    for _ in range(2):
        for device_id in customers:
            add_to_cart(client, ids["latte"], "M", device_id=device_id)
        responses = _parallel(
            lambda index: client.post("/api/orders", headers=device(customers[index])), 6
        )
        assert [response.status_code for response in responses] == [201] * 6
        codes = sorted(response.json()["code"] for response in responses)
        assert codes == [f"A-{number:03d}" for number in range(expected + 1, expected + 7)]
        expected += 6
        with engine.begin() as connection:
            connection.execute(text("UPDATE orders SET status = 'PICKED_UP'"))


def test_double_submit_of_one_customer_makes_one_order(client, ids, engine):
    add_to_cart(client, ids["latte"], "M", 2)
    responses = _parallel(lambda _: client.post("/api/orders", headers=device()), 5)

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409, 409, 409, 409]
    created = next(response for response in responses if response.status_code == 201).json()
    for response in responses:
        if response.status_code == 409:
            error = error_of(response)
            assert error["code"] == "ACTIVE_ORDER_EXISTS"
            assert error["details"] == {
                "order_id": created["id"],
                "code": created["code"],
                "status": "NEW",
            }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM orders")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM order_items")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM order_events")).scalar() == 1


def test_checkout_racing_with_add_to_cart_never_loses_or_duplicates_lines(client, ids, engine):
    """A line added while checkout runs lands either in the order or in the new cart."""
    add_to_cart(client, ids["latte"], "M", 1)

    def act(index: int):
        if index == 0:
            return client.post("/api/orders", headers=device())
        return client.post(
            "/api/cart/items",
            json={"menu_item_id": ids["cheesecake"], "size": "M", "qty": 1},
            headers=device(),
        )

    responses = _parallel(act, 2)
    assert responses[0].status_code == 201
    assert responses[1].status_code == 200
    order_lines = responses[0].json()["items"]
    with engine.connect() as connection:
        cart_qty = connection.execute(
            text("SELECT COALESCE(SUM(qty), 0) FROM cart_items WHERE menu_item_id = :id"),
            {"id": ids["cheesecake"]},
        ).scalar()
    in_order = sum(line["qty"] for line in order_lines if line["name"] == "Cheesecake")
    assert in_order + cart_qty == 1  # exactly one cheesecake, in one place only


def test_customer_row_is_created_once_for_parallel_checkouts_of_a_new_device(client, ids, engine):
    responses = _parallel(lambda _: client.post("/api/orders", headers=device(DEVICE_A)), 4)
    assert {response.status_code for response in responses} == {409}
    assert {error_of(response)["code"] for response in responses} == {"CART_EMPTY"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM customers")).scalar() == 1
