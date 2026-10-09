"""GET /api/menu: shape, order, stop-list, sizes."""

from sqlalchemy import text

from tests.integration.api_helpers import device, error_of, seed_menu


def test_menu_shape_and_order(client, engine):
    ids = seed_menu(engine)
    response = client.get("/api/menu", headers=device())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items"}
    # coffee, tea, cake; by name inside a category
    assert [item["name"] for item in body["items"]] == [
        "Espresso",
        "Latte",
        "Green Tea",
        "Cheesecake",
        "Ghost Pie",
    ]
    assert body["items"][1] == {
        "id": ids["latte"],
        "name": "Latte",
        "category": "coffee",
        "sizes": [
            {"size": "S", "price_amd": 1100},
            {"size": "M", "price_amd": 1300},
            {"size": "L", "price_amd": 1500},
        ],
        "is_available": True,
        "image_url": "/media/menu/latte.svg",
    }


def test_sizes_list_only_offered_sizes_in_s_m_l_order(client, engine):
    seed_menu(engine)
    items = {i["name"]: i for i in client.get("/api/menu", headers=device()).json()["items"]}
    assert items["Espresso"]["sizes"] == [
        {"size": "M", "price_amd": 900},
        {"size": "L", "price_amd": 1100},
    ]
    assert items["Green Tea"]["sizes"] == [{"size": "M", "price_amd": 700}]


def test_stop_list_items_are_included_and_flagged(client, engine):
    seed_menu(engine)
    items = {i["name"]: i for i in client.get("/api/menu", headers=device()).json()["items"]}
    assert items["Ghost Pie"]["is_available"] is False
    assert items["Latte"]["is_available"] is True


def test_missing_image_is_null(client, engine):
    seed_menu(engine)
    with engine.begin() as connection:
        connection.execute(text("UPDATE menu_items SET image_url = NULL WHERE name = 'Latte'"))
    items = {i["name"]: i for i in client.get("/api/menu", headers=device()).json()["items"]}
    assert items["Latte"]["image_url"] is None


def test_empty_menu_is_an_empty_list(client):
    assert client.get("/api/menu", headers=device()).json() == {"items": []}


def test_menu_rejects_other_methods(client):
    response = client.post("/api/menu", headers=device())
    assert response.status_code == 405
    assert error_of(response)["code"] == "METHOD_NOT_ALLOWED"
