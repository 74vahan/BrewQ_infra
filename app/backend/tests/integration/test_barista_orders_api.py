"""Barista queue, today's list and the status machine over HTTP."""

import itertools

import pytest
from sqlalchemy import text

from app.domain.order_status import Actor, OrderStatus, allowed_targets
from tests.integration.api_helpers import (
    DEVICE_A,
    DEVICE_B,
    TIMESTAMP_RE,
    add_to_cart,
    barista_login,
    device,
    error_of,
    make_device_id,
    place_order,
    seed_menu,
)
from tests.integration.helpers import utc

ARMENIAN_NAME = "".join(chr(c) for c in (0x531, 0x576, 0x56B))
TARGETS = ["IN_PROGRESS", "READY", "PICKED_UP", "CANCELLED"]


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


@pytest.fixture
def barista(client):
    return barista_login(client)


def _make_order(client, ids, device_id=DEVICE_A, key="latte", qty=1) -> dict:
    add_to_cart(client, ids[key], "M", qty, device_id=device_id)
    return place_order(client, device_id)


def _set_status(engine, order_id: int, status: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = :s WHERE id = :id"), {"s": status, "id": order_id}
        )


def _status(client, barista, order_id: int, to: str):
    return client.post(f"/api/barista/orders/{order_id}/status", json={"to": to}, headers=barista)


def _events(engine) -> list[tuple]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT order_id, from_status, to_status FROM order_events ORDER BY id")
        ).all()
    return [tuple(row) for row in rows]


# --- the queue (scope=active) ----------------------------------------------------------------


def test_empty_queue(client, barista):
    response = client.get("/api/barista/orders", headers=barista)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_queue_item_has_the_barista_order_shape(client, ids, barista, clock):
    client.put("/api/me", json={"name": ARMENIAN_NAME}, headers=device())
    order = _make_order(client, ids, qty=2)
    body = client.get("/api/barista/orders", headers=barista).json()
    assert set(body) == {"items"}
    (item,) = body["items"]
    assert set(item) == {
        "id",
        "code",
        "status",
        "total_amd",
        "created_at",
        "updated_at",
        "customer_name",
        "allowed_transitions",
        "items",
    }
    assert "can_cancel" not in item
    assert item["id"] == order["id"]
    assert item["code"] == "A-001"
    assert item["status"] == "NEW"
    assert item["customer_name"] == ARMENIAN_NAME
    assert item["allowed_transitions"] == ["IN_PROGRESS", "CANCELLED"]
    assert TIMESTAMP_RE.match(item["created_at"])
    assert item["items"] == order["items"]
    assert item["total_amd"] == 2600


def test_customer_name_is_null_when_not_given(client, ids, barista):
    _make_order(client, ids)
    assert (
        client.get("/api/barista/orders", headers=barista).json()["items"][0]["customer_name"]
        is None
    )


def test_queue_is_oldest_first_and_holds_only_active_orders(client, ids, engine, clock, barista):
    created = []
    for number in range(1, 6):
        clock.advance(minutes=2)
        created.append(_make_order(client, ids, make_device_id(number)))
    _set_status(engine, created[1]["id"], "PICKED_UP")
    _set_status(engine, created[3]["id"], "CANCELLED")
    _set_status(engine, created[2]["id"], "READY")
    body = client.get("/api/barista/orders", params={"scope": "active"}, headers=barista).json()
    assert [order["code"] for order in body["items"]] == ["A-001", "A-003", "A-005"]
    assert [order["status"] for order in body["items"]] == ["NEW", "READY", "NEW"]


def test_scope_defaults_to_active(client, ids, engine, barista):
    done = _make_order(client, ids, DEVICE_A)
    _set_status(engine, done["id"], "PICKED_UP")
    live = _make_order(client, ids, DEVICE_B)
    body = client.get("/api/barista/orders", headers=barista).json()
    assert [order["id"] for order in body["items"]] == [live["id"]]


@pytest.mark.parametrize("scope", ["", "all", "ACTIVE", "yesterday", "active,today"])
def test_unknown_scope_is_400(client, barista, scope):
    response = client.get("/api/barista/orders", params={"scope": scope}, headers=barista)
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


# --- scope=today (Yerevan day) ---------------------------------------------------------------


def test_today_lists_every_status_newest_first(client, ids, engine, clock, barista):
    created = []
    for number in range(1, 5):
        clock.advance(minutes=1)
        created.append(_make_order(client, ids, make_device_id(number)))
    _set_status(engine, created[0]["id"], "PICKED_UP")
    _set_status(engine, created[1]["id"], "CANCELLED")
    body = client.get("/api/barista/orders", params={"scope": "today"}, headers=barista).json()
    assert [order["code"] for order in body["items"]] == ["A-004", "A-003", "A-002", "A-001"]
    assert [order["status"] for order in body["items"]] == [
        "NEW",
        "NEW",
        "CANCELLED",
        "PICKED_UP",
    ]
    cancelled = body["items"][2]
    assert cancelled["allowed_transitions"] == []


def test_today_is_cut_at_the_yerevan_midnight(client, ids, engine, clock, barista):
    # Yerevan 2026-10-09 = [2026-10-08 20:00 UTC, 2026-10-09 20:00 UTC)
    moments = {
        "yesterday_last": utc(2026, 10, 8, 19, 59, 59),
        "today_first": utc(2026, 10, 8, 20, 0, 0),
        "today_last": utc(2026, 10, 9, 19, 59, 59),
        "tomorrow_first": utc(2026, 10, 9, 20, 0, 0),
    }
    for number, (label, moment) in enumerate(moments.items(), start=1):
        clock.set(moment)
        order = _make_order(client, ids, make_device_id(number))
        _set_status(engine, order["id"], "PICKED_UP")
        moments[label] = order["id"]

    clock.set(utc(2026, 10, 9, 8, 0))  # midday of Yerevan 2026-10-09
    ids_today = [
        order["id"]
        for order in client.get(
            "/api/barista/orders", params={"scope": "today"}, headers=barista
        ).json()["items"]
    ]
    assert ids_today == [moments["today_last"], moments["today_first"]]

    clock.set(utc(2026, 10, 9, 20, 0, 1))  # a second into the next Yerevan day
    barista = barista_login(client)  # the first token has just expired (12 h)
    ids_next = [
        order["id"]
        for order in client.get(
            "/api/barista/orders", params={"scope": "today"}, headers=barista
        ).json()["items"]
    ]
    assert ids_next == [moments["tomorrow_first"]]


def test_the_queue_is_not_limited_to_today(client, ids, engine, clock, barista):
    clock.set(utc(2026, 10, 7, 8, 0))
    old = _make_order(client, ids)
    clock.set(utc(2026, 10, 9, 8, 0))
    active = client.get("/api/barista/orders", headers=barista).json()["items"]
    today = client.get("/api/barista/orders", params={"scope": "today"}, headers=barista)
    assert [order["id"] for order in active] == [old["id"]]  # still waiting, from two days ago
    assert today.json()["items"] == []


# --- status changes ----------------------------------------------------------------------------


def test_the_full_happy_path_is_visible_to_the_client(client, ids, engine, clock, barista):
    order = _make_order(client, ids)
    for step, target in enumerate(["IN_PROGRESS", "READY", "PICKED_UP"], start=1):
        clock.advance(minutes=step)
        response = _status(client, barista, order["id"], target)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == target
        assert "can_cancel" not in body
        assert body["updated_at"] != body["created_at"]
        seen = client.get(f"/api/orders/{order['id']}", headers=device()).json()
        assert seen["status"] == target
        assert seen["updated_at"] == body["updated_at"]
    assert _events(engine) == [
        (order["id"], None, "NEW"),
        (order["id"], "NEW", "IN_PROGRESS"),
        (order["id"], "IN_PROGRESS", "READY"),
        (order["id"], "READY", "PICKED_UP"),
    ]
    assert client.get("/api/orders/current", headers=device()).json() == {"order": None}


def test_status_response_is_a_full_barista_order(client, ids, barista):
    order = _make_order(client, ids)
    body = _status(client, barista, order["id"], "IN_PROGRESS").json()
    assert set(body) == {
        "id",
        "code",
        "status",
        "total_amd",
        "created_at",
        "updated_at",
        "customer_name",
        "allowed_transitions",
        "items",
    }
    assert body["allowed_transitions"] == ["READY", "CANCELLED"]


def test_updated_at_is_the_time_of_the_change(client, ids, clock, barista):
    order = _make_order(client, ids)
    clock.advance(minutes=7, seconds=30)
    body = _status(client, barista, order["id"], "IN_PROGRESS").json()
    assert body["created_at"] == "2026-10-09T08:00:00.000000Z"
    assert body["updated_at"] == "2026-10-09T08:07:30.000000Z"


ALL_PAIRS = list(itertools.product([s.value for s in OrderStatus], TARGETS))


@pytest.mark.parametrize(("current", "target"), ALL_PAIRS)
def test_transition_table_over_http(client, ids, engine, barista, current, target):
    order = _make_order(client, ids)
    _set_status(engine, order["id"], current)
    events_before = _events(engine)

    response = _status(client, barista, order["id"], target)

    allowed = [s.value for s in allowed_targets(OrderStatus(current), Actor.BARISTA)]
    with engine.connect() as connection:
        stored = connection.execute(text("SELECT status FROM orders")).scalar()
    if target in allowed:
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target
        assert stored == target
        assert _events(engine) == [*events_before, (order["id"], current, target)]
    else:
        assert response.status_code == 409
        error = error_of(response)
        assert error["code"] == "INVALID_STATUS_TRANSITION"
        assert error["details"] == {"from": current, "to": target, "allowed": allowed}
        assert stored == current  # untouched
        assert _events(engine) == events_before  # no event for a refused change


def test_the_documented_example_of_the_error_details(client, ids, engine, barista):
    order = _make_order(client, ids)
    _set_status(engine, order["id"], "READY")
    response = _status(client, barista, order["id"], "IN_PROGRESS")
    assert error_of(response)["details"] == {
        "from": "READY",
        "to": "IN_PROGRESS",
        "allowed": ["PICKED_UP"],
    }


def test_a_repeated_press_gets_409_instead_of_advancing_again(client, ids, engine, barista):
    order = _make_order(client, ids)
    assert _status(client, barista, order["id"], "IN_PROGRESS").status_code == 200
    again = _status(client, barista, order["id"], "IN_PROGRESS")
    assert again.status_code == 409
    assert error_of(again)["details"]["from"] == "IN_PROGRESS"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM orders")).scalar() == "IN_PROGRESS"
    assert len(_events(engine)) == 2


def test_the_barista_can_cancel_new_and_in_progress_but_not_ready(client, ids, engine, barista):
    for number, start in enumerate(["NEW", "IN_PROGRESS", "READY"], start=1):
        order = _make_order(client, ids, make_device_id(number))
        _set_status(engine, order["id"], start)
        response = _status(client, barista, order["id"], "CANCELLED")
        assert response.status_code == (409 if start == "READY" else 200), start


def test_cancelling_frees_the_client_for_a_new_order(client, ids, barista):
    order = _make_order(client, ids)
    _status(client, barista, order["id"], "CANCELLED")
    seen = client.get(f"/api/orders/{order['id']}", headers=device()).json()
    assert seen["status"] == "CANCELLED"
    assert client.get("/api/orders/current", headers=device()).json() == {"order": None}


def test_unknown_order_is_404(client, barista):
    response = _status(client, barista, 424242, "IN_PROGRESS")
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "ORDER_NOT_FOUND"
    assert error["details"] == {"order_id": 424242}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"to": "NEW"},
        {"to": "in_progress"},
        {"to": "DONE"},
        {"to": None},
        {"to": 1},
        {"to": "READY", "extra": True},
        [],
    ],
)
def test_status_body_is_validated(client, ids, engine, barista, body):
    order = _make_order(client, ids)
    response = client.post(f"/api/barista/orders/{order['id']}/status", json=body, headers=barista)
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM orders")).scalar() == "NEW"


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1"])
def test_malformed_order_id_is_400(client, barista, bad_id):
    response = client.post(
        f"/api/barista/orders/{bad_id}/status", json={"to": "READY"}, headers=barista
    )
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_the_barista_sees_orders_of_every_customer(client, ids, barista):
    _make_order(client, ids, DEVICE_A)
    _make_order(client, ids, DEVICE_B)
    body = client.get("/api/barista/orders", headers=barista).json()
    assert [order["code"] for order in body["items"]] == ["A-001", "A-002"]
