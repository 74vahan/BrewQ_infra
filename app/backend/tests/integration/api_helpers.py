"""Helpers for API-level tests: device headers, menu fixtures, short request wrappers."""

import re
import secrets
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.integration.helpers import insert_menu_item

DEVICE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DEVICE_B = "bbbbbbbb-bbbb-4bbb-9bbb-bbbbbbbbbbbb"

# Throwaway credentials, generated per test run (nothing secret is committed).
BARISTA_PASSWORD = "pw-" + secrets.token_hex(8)
BARISTA_TOKEN_SECRET = secrets.token_hex(32)

# "2026-10-09T08:15:30.123456Z": six fractional digits and a literal Z.
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def device(device_id: str = DEVICE_A) -> dict[str, str]:
    return {"X-Device-Id": device_id}


def make_device_id(number: int) -> str:
    """A valid UUID v4 that is distinct per number."""
    return f"{number:08x}-0000-4000-8000-{number:012x}"


def seed_menu(engine: Engine) -> dict[str, int]:
    """Five items: three sizes, two sizes, one size (cake), a tea and a stop-listed item."""
    items = {
        "latte": {
            "name": "Latte",
            "category": "coffee",
            "price_s": 1100,
            "price_m": 1300,
            "price_l": 1500,
        },
        "espresso": {
            "name": "Espresso",
            "category": "coffee",
            "price_s": None,
            "price_m": 900,
            "price_l": 1100,
        },
        "green": {
            "name": "Green Tea",
            "category": "tea",
            "price_s": None,
            "price_m": 700,
            "price_l": None,
        },
        "cheesecake": {
            "name": "Cheesecake",
            "category": "cake",
            "price_s": None,
            "price_m": 1800,
            "price_l": None,
        },
        "ghost": {
            "name": "Ghost Pie",
            "category": "cake",
            "price_s": None,
            "price_m": 2000,
            "price_l": None,
        },
    }
    ids: dict[str, int] = {}
    with engine.begin() as connection:
        for key, values in items.items():
            ids[key] = insert_menu_item(connection, image_url=f"/media/menu/{key}.svg", **values)
        connection.execute(
            text("UPDATE menu_items SET is_available = FALSE WHERE id = :id"), {"id": ids["ghost"]}
        )
    return ids


def add_to_cart(
    client: TestClient,
    menu_item_id: int,
    size: str = "M",
    qty: int = 1,
    device_id: str = DEVICE_A,
) -> dict[str, Any]:
    response = client.post(
        "/api/cart/items",
        json={"menu_item_id": menu_item_id, "size": size, "qty": qty},
        headers=device(device_id),
    )
    assert response.status_code == 200, response.text
    return response.json()


def place_order(client: TestClient, device_id: str = DEVICE_A) -> dict[str, Any]:
    response = client.post("/api/orders", headers=device(device_id))
    assert response.status_code == 201, response.text
    return response.json()


def error_of(response) -> dict[str, Any]:
    body = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message", "details"}, body
    assert isinstance(body["error"]["details"], dict)
    return body["error"]


def barista_login(client: TestClient, password: str = BARISTA_PASSWORD) -> dict[str, str]:
    """Authorization header of a freshly logged-in barista."""
    response = client.post("/api/barista/login", json={"password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
