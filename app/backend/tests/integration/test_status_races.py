"""Races on one order: compare-and-set must give exactly one winner and one event."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import (
    add_to_cart,
    barista_login,
    device,
    error_of,
    make_device_id,
    place_order,
    seed_menu,
)

ROUNDS = 12


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


def _race(actions) -> list:
    barrier = Barrier(len(actions))

    def run(action):
        barrier.wait()
        return action()

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(run, actions))


def _cancel_vs_start(client, barista, order_id: int, device_id: str):
    """The client cancels while the barista starts the same order, released together."""
    return _race(
        [
            lambda: client.post(f"/api/orders/{order_id}/cancel", headers=device(device_id)),
            lambda: client.post(
                f"/api/barista/orders/{order_id}/status",
                json={"to": "IN_PROGRESS"},
                headers=barista,
            ),
        ]
    )


def _events(engine, order_id: int) -> list[tuple]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT from_status, to_status FROM order_events WHERE order_id = :id ORDER BY id"
            ),
            {"id": order_id},
        ).all()
    return [tuple(row) for row in rows]


def _status(engine, order_id: int) -> str:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT status FROM orders WHERE id = :id"), {"id": order_id}
        ).scalar()


def test_client_cancel_versus_barista_start_has_exactly_one_winner(client, ids, engine):
    barista = barista_login(client)
    outcomes = set()
    for round_number in range(ROUNDS):
        device_id = make_device_id(round_number + 1)
        add_to_cart(client, ids["latte"], "M", device_id=device_id)
        order = place_order(client, device_id)

        cancel, start = _cancel_vs_start(client, barista, order["id"], device_id)
        assert sorted([cancel.status_code, start.status_code]) == [200, 409], (
            cancel.text,
            start.text,
        )
        events = _events(engine, order["id"])
        assert len(events) == 2  # creation + exactly one change
        if cancel.status_code == 200:
            outcomes.add("client")
            assert _status(engine, order["id"]) == "CANCELLED"
            assert events[1] == ("NEW", "CANCELLED")
            assert error_of(start)["code"] == "INVALID_STATUS_TRANSITION"
            assert error_of(start)["details"]["from"] == "CANCELLED"
        else:
            outcomes.add("barista")
            assert _status(engine, order["id"]) == "IN_PROGRESS"
            assert events[1] == ("NEW", "IN_PROGRESS")
            assert error_of(cancel)["code"] == "ORDER_NOT_CANCELLABLE"
            assert error_of(cancel)["details"] == {"status": "IN_PROGRESS"}
    # Which side wins is the database's call and varies; each round was consistent either way.
    assert outcomes


def test_two_baristas_pressing_the_same_button_advance_the_order_once(client, ids, engine):
    barista = barista_login(client)
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    responses = _race(
        [
            lambda: client.post(
                f"/api/barista/orders/{order['id']}/status",
                json={"to": "IN_PROGRESS"},
                headers=barista,
            )
            for _ in range(4)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409, 409, 409]
    assert _status(engine, order["id"]) == "IN_PROGRESS"
    assert _events(engine, order["id"]) == [(None, "NEW"), ("NEW", "IN_PROGRESS")]


def test_barista_cancel_versus_barista_start_never_gives_two_changes(client, ids, engine):
    barista = barista_login(client)
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    cancel, start = _race(
        [
            lambda: client.post(
                f"/api/barista/orders/{order['id']}/status",
                json={"to": "CANCELLED"},
                headers=barista,
            ),
            lambda: client.post(
                f"/api/barista/orders/{order['id']}/status",
                json={"to": "IN_PROGRESS"},
                headers=barista,
            ),
        ]
    )
    # CANCELLED is reachable from both NEW and IN_PROGRESS, so both can succeed in sequence
    # (start first, then cancel); what must never happen is a lost or duplicated change.
    events = _events(engine, order["id"])
    final = _status(engine, order["id"])
    if (cancel.status_code, start.status_code) == (200, 200):
        assert events == [(None, "NEW"), ("NEW", "IN_PROGRESS"), ("IN_PROGRESS", "CANCELLED")]
        assert final == "CANCELLED"
    else:
        assert sorted([cancel.status_code, start.status_code]) == [200, 409]
        assert len(events) == 2
