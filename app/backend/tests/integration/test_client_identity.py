"""X-Device-Id: required, validated, normalized; the first request creates the customer."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

from tests.integration.api_helpers import DEVICE_A, DEVICE_B, device, error_of

CLIENT_ENDPOINTS = [
    ("GET", "/api/menu"),
    ("GET", "/api/me"),
    ("PUT", "/api/me"),
    ("GET", "/api/cart"),
    ("POST", "/api/cart/items"),
    ("PATCH", "/api/cart/items/1"),
    ("DELETE", "/api/cart/items/1"),
    ("DELETE", "/api/cart"),
    ("POST", "/api/orders"),
    ("GET", "/api/orders/current"),
    ("GET", "/api/orders/1"),
    ("GET", "/api/orders"),
    ("POST", "/api/orders/1/cancel"),
]


@pytest.mark.parametrize(("method", "path"), CLIENT_ENDPOINTS)
def test_missing_header_is_400_on_every_client_endpoint(client, method, path):
    response = client.request(method, path, json={} if method in {"PUT", "POST", "PATCH"} else None)
    assert response.status_code == 400
    error = error_of(response)
    assert error["code"] == "DEVICE_ID_MISSING"
    assert error["details"] == {}


@pytest.mark.parametrize(("method", "path"), CLIENT_ENDPOINTS)
def test_invalid_header_is_400_on_every_client_endpoint(client, method, path):
    response = client.request(method, path, headers=device("not-a-uuid"))
    assert response.status_code == 400
    assert error_of(response)["code"] == "DEVICE_ID_INVALID"


def test_empty_header_counts_as_missing(client):
    response = client.get("/api/me", headers={"X-Device-Id": ""})
    assert error_of(response)["code"] == "DEVICE_ID_MISSING"


@pytest.mark.parametrize(
    "bad",
    [
        "aaaaaaaa-aaaa-1aaa-8aaa-aaaaaaaaaaaa",  # UUID v1
        "aaaaaaaa-aaaa-4aaa-0aaa-aaaaaaaaaaaa",  # not the RFC 4122 variant
        "aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa",  # no hyphens
    ],
)
def test_only_uuid_v4_is_accepted(client, bad):
    response = client.get("/api/me", headers=device(bad))
    assert error_of(response)["code"] == "DEVICE_ID_INVALID"


def test_health_and_unknown_routes_do_not_need_the_header(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health/ready").status_code == 200
    assert error_of(client.get("/api/nope"))["code"] == "NOT_FOUND"


def test_first_request_creates_the_customer_and_later_ones_reuse_it(client, engine, clock):
    assert client.get("/api/me", headers=device()).status_code == 200
    assert client.get("/api/me", headers=device()).status_code == 200
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT device_id, name, created_at FROM customers")).all()
    assert len(rows) == 1
    assert rows[0].device_id == DEVICE_A
    assert rows[0].name is None
    assert rows[0].created_at == clock.now().replace(tzinfo=None)


def test_device_id_is_case_insensitive_and_stored_in_lower_case(client, engine):
    response = client.put("/api/me", json={"name": "Ani"}, headers=device(DEVICE_A.upper()))
    assert response.json() == {"name": "Ani"}
    assert client.get("/api/me", headers=device(DEVICE_A)).json() == {"name": "Ani"}
    with engine.connect() as connection:
        stored = connection.execute(text("SELECT device_id FROM customers")).scalars().all()
    assert stored == [DEVICE_A]


def test_different_devices_are_different_customers(client, engine):
    client.put("/api/me", json={"name": "Ani"}, headers=device(DEVICE_A))
    assert client.get("/api/me", headers=device(DEVICE_B)).json() == {"name": None}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM customers")).scalar() == 2


def test_parallel_first_requests_create_exactly_one_customer(client, engine):
    def hit(_):
        return client.get("/api/me", headers=device()).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(hit, range(8)))
    assert statuses == [200] * 8
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM customers")).scalar() == 1
