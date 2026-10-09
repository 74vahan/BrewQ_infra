"""Barista menu: the full list and the stop-list switch."""

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import (
    add_to_cart,
    barista_login,
    device,
    error_of,
    place_order,
    seed_menu,
)


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


@pytest.fixture
def barista(client):
    return barista_login(client)


def _row(engine, menu_item_id: int):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT * FROM menu_items WHERE id = :id"), {"id": menu_item_id}
        ).one()


def test_barista_menu_matches_the_client_menu(client, ids, barista):
    barista_menu = client.get("/api/barista/menu", headers=barista)
    client_menu = client.get("/api/menu", headers=device())
    assert barista_menu.status_code == 200
    assert barista_menu.json() == client_menu.json()
    names = [item["name"] for item in barista_menu.json()["items"]]
    assert names == ["Espresso", "Latte", "Green Tea", "Cheesecake", "Ghost Pie"]


def test_barista_menu_includes_the_stop_list(client, ids, barista):
    items = {i["name"]: i for i in client.get("/api/barista/menu", headers=barista).json()["items"]}
    assert items["Ghost Pie"]["is_available"] is False


def test_patch_puts_an_item_on_the_stop_list_and_back(client, ids, engine, barista):
    path = f"/api/barista/menu/{ids['latte']}"
    off = client.patch(path, json={"is_available": False}, headers=barista)
    assert off.status_code == 200
    body = off.json()
    assert body["id"] == ids["latte"]
    assert body["name"] == "Latte"
    assert body["is_available"] is False
    assert set(body) == {"id", "name", "category", "sizes", "is_available", "image_url"}
    assert _row(engine, ids["latte"]).is_available == 0
    # the clients see it at once
    latte = next(
        i for i in client.get("/api/menu", headers=device()).json()["items"] if i["name"] == "Latte"
    )
    assert latte["is_available"] is False

    on = client.patch(path, json={"is_available": True}, headers=barista)
    assert on.json()["is_available"] is True
    assert _row(engine, ids["latte"]).is_available == 1


def test_patch_changes_nothing_but_is_available(client, ids, engine, barista):
    before = _row(engine, ids["latte"])
    client.patch(f"/api/barista/menu/{ids['latte']}", json={"is_available": False}, headers=barista)
    after = _row(engine, ids["latte"])
    changed = {key for key in before._mapping if before._mapping[key] != after._mapping[key]}
    assert changed == {"is_available"}


def test_patch_is_idempotent(client, ids, barista):
    path = f"/api/barista/menu/{ids['latte']}"
    for _ in range(2):
        response = client.patch(path, json={"is_available": False}, headers=barista)
        assert response.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"is_available": False, "name": "Hacked"},
        {"is_available": False, "price_m": 1},
        {"is_available": False, "category": "tea"},
        {"is_available": False, "image_url": None},
        {"name": "Hacked"},
        {"is_available": "false"},
        {"is_available": 0},
        {"is_available": None},
        [],
    ],
)
def test_patch_rejects_anything_but_a_boolean_is_available(client, ids, engine, barista, body):
    before = _row(engine, ids["latte"])
    response = client.patch(f"/api/barista/menu/{ids['latte']}", json=body, headers=barista)
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    assert _row(engine, ids["latte"]) == before


def test_patch_unknown_item_is_404(client, ids, barista):
    response = client.patch(
        "/api/barista/menu/99999", json={"is_available": False}, headers=barista
    )
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "MENU_ITEM_NOT_FOUND"
    assert error["details"] == {"menu_item_id": 99999}


@pytest.mark.parametrize("bad_id", ["abc", "0", "-3"])
def test_patch_malformed_id_is_400(client, barista, bad_id):
    response = client.patch(
        f"/api/barista/menu/{bad_id}", json={"is_available": False}, headers=barista
    )
    assert response.status_code == 400


def test_stop_list_stops_new_cart_additions_and_checkout(client, ids, barista):
    add_to_cart(client, ids["latte"], "M")
    client.patch(f"/api/barista/menu/{ids['latte']}", json={"is_available": False}, headers=barista)
    again = client.post(
        "/api/cart/items", json={"menu_item_id": ids["latte"], "size": "M"}, headers=device()
    )
    assert error_of(again)["code"] == "MENU_ITEM_UNAVAILABLE"
    checkout = client.post("/api/orders", headers=device())
    assert error_of(checkout)["code"] == "CART_HAS_UNAVAILABLE_ITEMS"

    client.patch(f"/api/barista/menu/{ids['latte']}", json={"is_available": True}, headers=barista)
    assert place_order(client)["code"] == "A-001"


def test_the_stop_list_does_not_touch_orders_already_placed(client, ids, barista):
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    client.patch(f"/api/barista/menu/{ids['latte']}", json={"is_available": False}, headers=barista)
    seen = client.get(f"/api/orders/{order['id']}", headers=device()).json()
    assert seen["status"] == "NEW"
    assert seen["items"][0]["name"] == "Latte"
