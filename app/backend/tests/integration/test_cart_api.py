"""The five cart endpoints, their error codes and the add-to-cart race."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import (
    DEVICE_A,
    DEVICE_B,
    add_to_cart,
    device,
    error_of,
    seed_menu,
)


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


def test_empty_cart_shape(client):
    response = client.get("/api/cart", headers=device())
    assert response.status_code == 200
    assert response.json() == {"items": [], "total_amd": 0, "can_checkout": False}


def test_add_item_returns_the_cart_with_current_prices(client, ids):
    cart = add_to_cart(client, ids["latte"], "M", 2)
    assert set(cart) == {"items", "total_amd", "can_checkout"}
    (line,) = cart["items"]
    assert set(line) == {
        "id",
        "menu_item_id",
        "name",
        "image_url",
        "size",
        "qty",
        "unit_price_amd",
        "line_total_amd",
        "is_available",
        "problem",
    }
    assert line | {"id": 0} == {
        "id": 0,
        "menu_item_id": ids["latte"],
        "name": "Latte",
        "image_url": "/media/menu/latte.svg",
        "size": "M",
        "qty": 2,
        "unit_price_amd": 1300,
        "line_total_amd": 2600,
        "is_available": True,
        "problem": None,
    }
    assert cart["total_amd"] == 2600
    assert cart["can_checkout"] is True


def test_qty_defaults_to_one(client, ids):
    response = client.post(
        "/api/cart/items", json={"menu_item_id": ids["latte"], "size": "S"}, headers=device()
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["qty"] == 1


def test_adding_the_same_item_and_size_sums_the_quantity(client, ids):
    add_to_cart(client, ids["latte"], "M", 2)
    cart = add_to_cart(client, ids["latte"], "M", 3)
    assert [line["qty"] for line in cart["items"]] == [5]
    assert cart["total_amd"] == 5 * 1300


def test_other_size_or_item_is_a_separate_line_ordered_by_id(client, ids):
    add_to_cart(client, ids["latte"], "M")
    add_to_cart(client, ids["latte"], "L")
    cart = add_to_cart(client, ids["cheesecake"], "M")
    assert [(line["name"], line["size"]) for line in cart["items"]] == [
        ("Latte", "M"),
        ("Latte", "L"),
        ("Cheesecake", "M"),
    ]
    assert cart["items"] == sorted(cart["items"], key=lambda line: line["id"])
    assert cart["total_amd"] == 1300 + 1500 + 1800


def test_quantity_limit_is_20_per_line(client, ids):
    add_to_cart(client, ids["latte"], "M", 18)
    response = client.post(
        "/api/cart/items",
        json={"menu_item_id": ids["latte"], "size": "M", "qty": 3},
        headers=device(),
    )
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "CART_QTY_LIMIT_EXCEEDED"
    assert error["details"] == {"max": 20, "current": 18}
    # the failed add changed nothing, and exactly 20 is still allowed
    assert client.get("/api/cart", headers=device()).json()["items"][0]["qty"] == 18
    assert add_to_cart(client, ids["latte"], "M", 2)["items"][0]["qty"] == 20


def test_unknown_menu_item_is_404(client, ids):
    response = client.post(
        "/api/cart/items", json={"menu_item_id": 99999, "size": "M"}, headers=device()
    )
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "MENU_ITEM_NOT_FOUND"
    assert error["details"] == {"menu_item_id": 99999}


def test_stop_listed_item_cannot_be_added(client, ids):
    response = client.post(
        "/api/cart/items", json={"menu_item_id": ids["ghost"], "size": "M"}, headers=device()
    )
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "MENU_ITEM_UNAVAILABLE"
    assert error["details"] == {"menu_item_id": ids["ghost"]}


def test_size_without_a_price_is_rejected_and_lists_offered_sizes(client, ids):
    response = client.post(
        "/api/cart/items", json={"menu_item_id": ids["espresso"], "size": "S"}, headers=device()
    )
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "SIZE_NOT_OFFERED"
    assert error["details"] == {"menu_item_id": ids["espresso"], "size": "S", "offered": ["M", "L"]}
    assert client.get("/api/cart", headers=device()).json()["items"] == []


def test_single_size_item_accepts_only_m(client, ids):
    for size in ("S", "L"):
        response = client.post(
            "/api/cart/items", json={"menu_item_id": ids["green"], "size": size}, headers=device()
        )
        assert error_of(response)["code"] == "SIZE_NOT_OFFERED"
    assert add_to_cart(client, ids["green"], "M")["items"][0]["unit_price_amd"] == 700


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"size": "M"},
        {"menu_item_id": 1},
        {"menu_item_id": 1, "size": "XL"},
        {"menu_item_id": 1, "size": "m"},
        {"menu_item_id": 1, "size": "M", "qty": 0},
        {"menu_item_id": 1, "size": "M", "qty": 21},
        {"menu_item_id": 1, "size": "M", "qty": "2"},
        {"menu_item_id": 1, "size": "M", "qty": True},
        {"menu_item_id": 0, "size": "M"},
        {"menu_item_id": "1", "size": "M"},
        {"menu_item_id": 1, "size": "M", "extra": 1},
    ],
)
def test_add_validates_the_body(client, ids, body):
    response = client.post("/api/cart/items", json=body, headers=device())
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"]


def test_validation_error_names_the_field_and_the_issue(client, ids):
    response = client.post(
        "/api/cart/items",
        json={"menu_item_id": ids["latte"], "size": "M", "qty": 99},
        headers=device(),
    )
    assert error_of(response)["details"] == {
        "fields": [{"field": "qty", "issue": "less_than_equal"}]
    }


def test_malformed_json_is_400(client, ids):
    response = client.post(
        "/api/cart/items",
        content=b"{oops",
        headers={**device(), "content-type": "application/json"},
    )
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_patch_sets_the_quantity(client, ids):
    line_id = add_to_cart(client, ids["latte"], "M", 2)["items"][0]["id"]
    response = client.patch(f"/api/cart/items/{line_id}", json={"qty": 7}, headers=device())
    assert response.status_code == 200
    cart = response.json()
    assert cart["items"][0]["qty"] == 7
    assert cart["total_amd"] == 7 * 1300


@pytest.mark.parametrize("body", [{}, {"qty": 0}, {"qty": 21}, {"qty": "3"}, {"qty": 1, "x": 1}])
def test_patch_validates_the_body(client, ids, body):
    line_id = add_to_cart(client, ids["latte"], "M", 2)["items"][0]["id"]
    response = client.patch(f"/api/cart/items/{line_id}", json=body, headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_patch_unknown_line_is_404(client, ids):
    response = client.patch("/api/cart/items/99999", json={"qty": 2}, headers=device())
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "CART_ITEM_NOT_FOUND"
    assert error["details"] == {"cart_item_id": 99999}


def test_non_numeric_line_id_is_a_validation_error(client):
    response = client.patch("/api/cart/items/abc", json={"qty": 2}, headers=device())
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_delete_removes_one_line(client, ids):
    first = add_to_cart(client, ids["latte"], "M")["items"][0]["id"]
    add_to_cart(client, ids["cheesecake"], "M")
    response = client.delete(f"/api/cart/items/{first}", headers=device())
    assert response.status_code == 200
    assert [line["name"] for line in response.json()["items"]] == ["Cheesecake"]


def test_delete_unknown_line_is_404(client, ids):
    response = client.delete("/api/cart/items/99999", headers=device())
    assert response.status_code == 404
    assert error_of(response)["code"] == "CART_ITEM_NOT_FOUND"


def test_deleting_the_same_line_twice_is_404_the_second_time(client, ids):
    line_id = add_to_cart(client, ids["latte"], "M")["items"][0]["id"]
    assert client.delete(f"/api/cart/items/{line_id}", headers=device()).status_code == 200
    assert client.delete(f"/api/cart/items/{line_id}", headers=device()).status_code == 404


def test_delete_cart_empties_it(client, ids):
    add_to_cart(client, ids["latte"], "M")
    add_to_cart(client, ids["cheesecake"], "M")
    response = client.delete("/api/cart", headers=device())
    assert response.status_code == 200
    assert response.json() == {"items": [], "total_amd": 0, "can_checkout": False}
    assert client.delete("/api/cart", headers=device()).status_code == 200  # idempotent


def test_other_customers_lines_are_404_and_untouched(client, ids):
    line_id = add_to_cart(client, ids["latte"], "M", 2, device_id=DEVICE_A)["items"][0]["id"]
    patch = client.patch(f"/api/cart/items/{line_id}", json={"qty": 9}, headers=device(DEVICE_B))
    delete = client.delete(f"/api/cart/items/{line_id}", headers=device(DEVICE_B))
    assert error_of(patch)["code"] == "CART_ITEM_NOT_FOUND"
    assert error_of(delete)["code"] == "CART_ITEM_NOT_FOUND"
    assert client.get("/api/cart", headers=device(DEVICE_A)).json()["items"][0]["qty"] == 2


def test_carts_are_isolated_between_customers(client, ids):
    add_to_cart(client, ids["latte"], "M", device_id=DEVICE_A)
    assert client.get("/api/cart", headers=device(DEVICE_B)).json()["items"] == []
    client.delete("/api/cart", headers=device(DEVICE_B))
    assert len(client.get("/api/cart", headers=device(DEVICE_A)).json()["items"]) == 1


# --- stop-list and price changes after the item was added ------------------------------------


def test_item_stop_listed_after_adding_is_flagged_and_left_out_of_the_total(client, ids, engine):
    add_to_cart(client, ids["latte"], "M", 2)
    add_to_cart(client, ids["cheesecake"], "M", 1)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE menu_items SET is_available = FALSE WHERE id = :id"),
            {"id": ids["latte"]},
        )
    cart = client.get("/api/cart", headers=device()).json()
    latte, cake = cart["items"]
    assert latte["problem"] == "unavailable"
    assert latte["is_available"] is False
    assert latte["unit_price_amd"] == 1300  # the price is still known
    assert latte["line_total_amd"] == 2600
    assert cake["problem"] is None
    assert cart["total_amd"] == 1800
    assert cart["can_checkout"] is False


def test_size_removed_from_the_menu_after_adding_is_flagged(client, ids, engine):
    add_to_cart(client, ids["latte"], "S", 1)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE menu_items SET price_s = NULL WHERE id = :id"), {"id": ids["latte"]}
        )
    cart = client.get("/api/cart", headers=device()).json()
    (line,) = cart["items"]
    assert line["problem"] == "size_not_offered"
    assert line["unit_price_amd"] is None
    assert line["line_total_amd"] is None
    assert cart["total_amd"] == 0
    assert cart["can_checkout"] is False


def test_prices_in_the_cart_follow_the_current_menu(client, ids, engine):
    add_to_cart(client, ids["latte"], "M", 2)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE menu_items SET price_m = 1400 WHERE id = :id"), {"id": ids["latte"]}
        )
    cart = client.get("/api/cart", headers=device()).json()
    assert cart["items"][0]["unit_price_amd"] == 1400
    assert cart["total_amd"] == 2800


def test_a_fixed_cart_can_be_checked_out_again(client, ids, engine):
    add_to_cart(client, ids["latte"], "M")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE menu_items SET is_available = FALSE WHERE id = :id"), {"id": ids["latte"]}
        )
        connection.execute(
            text("UPDATE menu_items SET is_available = TRUE WHERE id = :id"), {"id": ids["latte"]}
        )
    assert client.get("/api/cart", headers=device()).json()["can_checkout"] is True


# --- concurrency -------------------------------------------------------------------------------


def test_parallel_adds_respect_the_limit_exactly(client, ids, engine):
    """Eight requests add 3 each: at most 6 fit under 20 (18), two must get 409."""
    workers = 8
    barrier = Barrier(workers)

    def add(_):
        barrier.wait()
        return client.post(
            "/api/cart/items",
            json={"menu_item_id": ids["latte"], "size": "M", "qty": 3},
            headers=device(),
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(add, range(workers)))
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] * 6 + [409] * 2
    for response in responses:
        if response.status_code == 409:
            assert error_of(response)["code"] == "CART_QTY_LIMIT_EXCEEDED"
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT qty FROM cart_items")).scalars().all()
    assert rows == [18]


def test_parallel_adds_of_a_new_line_create_exactly_one_row(client, ids, engine):
    workers = 6
    barrier = Barrier(workers)

    def add(_):
        barrier.wait()
        return client.post(
            "/api/cart/items",
            json={"menu_item_id": ids["cheesecake"], "size": "M", "qty": 1},
            headers=device(),
        ).status_code

    with ThreadPoolExecutor(max_workers=workers) as pool:
        statuses = list(pool.map(add, range(workers)))
    assert statuses == [200] * workers
    with engine.connect() as connection:
        assert connection.execute(text("SELECT qty FROM cart_items")).scalars().all() == [6]
