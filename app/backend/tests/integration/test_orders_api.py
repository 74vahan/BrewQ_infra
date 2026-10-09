"""Order reads (current, by id, history) and client cancellation."""

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import (
    DEVICE_A,
    DEVICE_B,
    TIMESTAMP_RE,
    add_to_cart,
    device,
    error_of,
    place_order,
    seed_menu,
)


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


def _set_status(engine, order_id: int, status: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = :s WHERE id = :id"), {"s": status, "id": order_id}
        )


def _order(client, ids, device_id=DEVICE_A, key="latte", engine=None, finish_with=None):
    """Create an order; optionally move it to a terminal status so another one can follow."""
    add_to_cart(client, ids[key], "M", device_id=device_id)
    order = place_order(client, device_id)
    if finish_with is not None:
        _set_status(engine, order["id"], finish_with)
    return order


# --- GET /api/orders/current ---------------------------------------------------------------


def test_no_active_order_gives_null(client):
    response = client.get("/api/orders/current", headers=device())
    assert response.status_code == 200
    assert response.json() == {"order": None}


@pytest.mark.parametrize("status", ["NEW", "IN_PROGRESS", "READY"])
def test_current_returns_the_active_order(client, ids, engine, status):
    order = _order(client, ids)
    _set_status(engine, order["id"], status)
    body = client.get("/api/orders/current", headers=device()).json()
    assert set(body) == {"order"}
    assert body["order"]["id"] == order["id"]
    assert body["order"]["status"] == status
    assert body["order"]["can_cancel"] is (status == "NEW")


@pytest.mark.parametrize("status", ["PICKED_UP", "CANCELLED"])
def test_finished_orders_are_not_current(client, ids, engine, status):
    order = _order(client, ids)
    _set_status(engine, order["id"], status)
    assert client.get("/api/orders/current", headers=device()).json() == {"order": None}


def test_current_is_per_customer(client, ids):
    _order(client, ids, DEVICE_A)
    assert client.get("/api/orders/current", headers=device(DEVICE_B)).json() == {"order": None}


# --- GET /api/orders/{id} ------------------------------------------------------------------


def test_get_order_returns_the_contract_shape(client, ids):
    order = _order(client, ids)
    response = client.get(f"/api/orders/{order['id']}", headers=device())
    assert response.status_code == 200
    body = response.json()
    assert body == order
    assert TIMESTAMP_RE.match(body["created_at"])
    assert TIMESTAMP_RE.match(body["updated_at"])


@pytest.mark.parametrize("status", ["IN_PROGRESS", "READY", "PICKED_UP", "CANCELLED"])
def test_get_order_works_in_every_status_and_reports_can_cancel(client, ids, engine, status):
    order = _order(client, ids)
    _set_status(engine, order["id"], status)
    body = client.get(f"/api/orders/{order['id']}", headers=device()).json()
    assert body["status"] == status
    assert body["can_cancel"] is False


def test_missing_order_is_404(client):
    response = client.get("/api/orders/424242", headers=device())
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "ORDER_NOT_FOUND"
    assert error["details"] == {"order_id": 424242}


def test_someone_elses_order_looks_exactly_like_a_missing_one(client, ids):
    order = _order(client, ids, DEVICE_A)
    foreign = client.get(f"/api/orders/{order['id']}", headers=device(DEVICE_B))
    missing = client.get("/api/orders/424242", headers=device(DEVICE_B))
    assert foreign.status_code == missing.status_code == 404
    foreign_error, missing_error = error_of(foreign), error_of(missing)
    assert foreign_error["code"] == missing_error["code"] == "ORDER_NOT_FOUND"
    assert foreign_error["details"] == {"order_id": order["id"]}


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "1.5"])
def test_malformed_order_id_is_a_validation_error(client, bad_id):
    response = client.get(f"/api/orders/{bad_id}", headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_an_oversized_order_id_is_a_validation_error_not_a_500(client):
    response = client.get(f"/api/orders/{2**70}", headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


# --- GET /api/orders (history, keyset) -----------------------------------------------------


def _make_history(client, ids, engine, count: int) -> list[int]:
    """`count` finished orders of DEVICE_A, oldest first; returns their ids."""
    created = []
    for _ in range(count):
        created.append(_order(client, ids, DEVICE_A, engine=engine, finish_with="PICKED_UP")["id"])
    return created


def test_history_of_a_new_customer_is_empty(client):
    response = client.get("/api/orders", headers=device())
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_before_id": None}


def test_history_is_newest_first_and_fully_shaped(client, ids, engine):
    created = _make_history(client, ids, engine, 3)
    body = client.get("/api/orders", headers=device()).json()
    assert set(body) == {"items", "next_before_id"}
    assert [order["id"] for order in body["items"]] == created[::-1]
    assert body["next_before_id"] is None
    assert set(body["items"][0]) == {
        "id",
        "code",
        "status",
        "total_amd",
        "created_at",
        "updated_at",
        "can_cancel",
        "items",
    }
    assert body["items"][0]["items"][0]["name"] == "Latte"


def test_history_keyset_pagination_walks_all_pages_without_gaps(client, ids, engine):
    created = _make_history(client, ids, engine, 5)
    seen: list[int] = []
    before_id = None
    pages = 0
    while True:
        params = {"limit": 2, **({"before_id": before_id} if before_id else {})}
        body = client.get("/api/orders", params=params, headers=device()).json()
        pages += 1
        seen += [order["id"] for order in body["items"]]
        before_id = body["next_before_id"]
        if before_id is None:
            break
    assert pages == 3
    assert seen == created[::-1]


def test_next_before_id_is_null_when_the_page_is_exactly_the_rest(client, ids, engine):
    _make_history(client, ids, engine, 4)
    first = client.get("/api/orders", params={"limit": 2}, headers=device()).json()
    assert first["next_before_id"] == first["items"][-1]["id"]
    second = client.get(
        "/api/orders",
        params={"limit": 2, "before_id": first["next_before_id"]},
        headers=device(),
    ).json()
    assert len(second["items"]) == 2
    assert second["next_before_id"] is None


def test_history_default_limit_is_20(client, ids, engine):
    _make_history(client, ids, engine, 22)
    body = client.get("/api/orders", headers=device()).json()
    assert len(body["items"]) == 20
    assert body["next_before_id"] == body["items"][-1]["id"]


def test_history_includes_the_active_order_and_every_status(client, ids, engine):
    _order(client, ids, engine=engine, finish_with="CANCELLED")
    _order(client, ids, engine=engine, finish_with="PICKED_UP")
    active = _order(client, ids)
    body = client.get("/api/orders", headers=device()).json()
    assert [order["status"] for order in body["items"]] == ["NEW", "PICKED_UP", "CANCELLED"]
    assert body["items"][0]["id"] == active["id"]


def test_history_shows_only_own_orders(client, ids, engine):
    _order(client, ids, DEVICE_A, engine=engine, finish_with="PICKED_UP")
    _order(client, ids, DEVICE_B)
    assert len(client.get("/api/orders", headers=device(DEVICE_A)).json()["items"]) == 1
    assert len(client.get("/api/orders", headers=device(DEVICE_B)).json()["items"]) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 51},
        {"limit": "abc"},
        {"before_id": 0},
        {"before_id": "x"},
        {"before_id": -5},
    ],
)
def test_history_validates_its_query(client, params):
    response = client.get("/api/orders", params=params, headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_limit_bounds_are_inclusive(client, ids, engine):
    _make_history(client, ids, engine, 2)
    assert client.get("/api/orders", params={"limit": 1}, headers=device()).status_code == 200
    assert client.get("/api/orders", params={"limit": 50}, headers=device()).status_code == 200


# --- POST /api/orders/{id}/cancel ----------------------------------------------------------


def test_client_can_cancel_a_new_order(client, ids, engine, clock):
    order = _order(client, ids)
    clock.advance(minutes=3)
    response = client.post(f"/api/orders/{order['id']}/cancel", headers=device())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["can_cancel"] is False
    assert body["id"] == order["id"]
    assert body["created_at"] == "2026-10-09T08:00:00.000000Z"
    assert body["updated_at"] == "2026-10-09T08:03:00.000000Z"
    with engine.connect() as connection:
        events = connection.execute(
            text("SELECT from_status, to_status FROM order_events ORDER BY id")
        ).all()
    assert [(event.from_status, event.to_status) for event in events] == [
        (None, "NEW"),
        ("NEW", "CANCELLED"),
    ]


def test_cancelling_frees_the_customer_for_a_new_order(client, ids):
    order = _order(client, ids)
    client.post(f"/api/orders/{order['id']}/cancel", headers=device())
    assert client.get("/api/orders/current", headers=device()).json() == {"order": None}
    add_to_cart(client, ids["latte"], "M")
    assert place_order(client)["code"] == "A-002"


@pytest.mark.parametrize("status", ["IN_PROGRESS", "READY", "PICKED_UP", "CANCELLED"])
def test_only_new_orders_can_be_cancelled(client, ids, engine, status):
    order = _order(client, ids)
    _set_status(engine, order["id"], status)
    response = client.post(f"/api/orders/{order['id']}/cancel", headers=device())
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "ORDER_NOT_CANCELLABLE"
    assert error["details"] == {"status": status}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM orders")).scalar() == status
        assert connection.execute(text("SELECT COUNT(*) FROM order_events")).scalar() == 1


def test_cancelling_twice_gives_409_the_second_time(client, ids, engine):
    order = _order(client, ids)
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=device()).status_code == 200
    second = client.post(f"/api/orders/{order['id']}/cancel", headers=device())
    assert second.status_code == 409
    assert error_of(second)["details"] == {"status": "CANCELLED"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM order_events")).scalar() == 2


def test_cancelling_a_missing_or_foreign_order_is_404(client, ids, engine):
    order = _order(client, ids, DEVICE_A)
    foreign = client.post(f"/api/orders/{order['id']}/cancel", headers=device(DEVICE_B))
    missing = client.post("/api/orders/424242/cancel", headers=device(DEVICE_B))
    assert error_of(foreign)["code"] == "ORDER_NOT_FOUND"
    assert error_of(missing)["code"] == "ORDER_NOT_FOUND"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM orders")).scalar() == "NEW"


def test_cancel_when_the_barista_already_moved_the_order_reports_the_real_status(
    client, ids, engine, monkeypatch
):
    """The row changes between our read and our UPDATE: compare-and-set must lose cleanly."""
    from app.repositories import orders as orders_repo

    order = _order(client, ids)
    real_get_own = orders_repo.get_own

    def get_own_then_barista_acts(session, customer_id, order_id):
        found = real_get_own(session, customer_id, order_id)
        _set_status(engine, order_id, "IN_PROGRESS")  # committed on another connection
        return found

    monkeypatch.setattr(orders_repo, "get_own", get_own_then_barista_acts)
    response = client.post(f"/api/orders/{order['id']}/cancel", headers=device())
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "ORDER_NOT_CANCELLABLE"
    assert error["details"] == {"status": "IN_PROGRESS"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM orders")).scalar() == "IN_PROGRESS"
        assert connection.execute(text("SELECT COUNT(*) FROM order_events")).scalar() == 1
