"""The retry loop of checkout, driven by injected database errors."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError

from app.services import checkout as checkout_module
from tests.integration.api_helpers import add_to_cart, device, error_of, place_order, seed_menu


class FakeDriverError(Exception):
    """Stands in for pymysql's error: SQLAlchemy reads `.args[0]` as the MySQL errno."""


def _db_error(errno: int, message: str, cls=DBAPIError) -> DBAPIError:
    return cls("INSERT ...", {}, FakeDriverError(errno, message))


@pytest.fixture
def ids(engine):
    return seed_menu(engine)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(checkout_module.time, "sleep", lambda _: None)


def _fail_first(monkeypatch, failures: int, error: DBAPIError):
    """Make _create_order raise `error` `failures` times, then behave normally."""
    real = checkout_module._create_order
    calls = {"count": 0}

    def flaky(session, customer_id, now):
        calls["count"] += 1
        if calls["count"] <= failures:
            raise error
        return real(session, customer_id, now)

    monkeypatch.setattr(checkout_module, "_create_order", flaky)
    return calls


def test_duplicate_code_is_retried_until_it_succeeds(client, ids, monkeypatch):
    error = _db_error(
        1062, "Duplicate entry '2026-10-09-A-001' for key 'orders.uq_orders_day_code'"
    )
    calls = _fail_first(monkeypatch, 3, error)
    add_to_cart(client, ids["latte"], "M")
    order = place_order(client)
    assert calls["count"] == 4
    assert order["code"] == "A-001"


def test_deadlock_is_retried(client, ids, monkeypatch):
    error = _db_error(1213, "Deadlock found when trying to get lock", OperationalError)
    calls = _fail_first(monkeypatch, 2, error)
    add_to_cart(client, ids["latte"], "M")
    assert place_order(client)["code"] == "A-001"
    assert calls["count"] == 3


def test_giving_up_is_a_500_envelope_and_keeps_the_cart(client, ids, engine, monkeypatch):
    error = _db_error(1062, "Duplicate entry 'x' for key 'orders.uq_orders_day_code'")
    calls = _fail_first(monkeypatch, 10**6, error)
    add_to_cart(client, ids["latte"], "M", 2)
    response = client.post("/api/orders", headers=device())
    assert response.status_code == 500
    envelope = error_of(response)
    assert envelope["code"] == "INTERNAL_ERROR"
    assert "Duplicate" not in response.text
    assert calls["count"] == checkout_module.MAX_ATTEMPTS
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM orders")).scalar() == 0
    assert client.get("/api/cart", headers=device()).json()["items"][0]["qty"] == 2


@pytest.mark.parametrize(
    "error",
    [
        _db_error(1062, "Duplicate entry 'x' for key 'customers.uq_customers_device_id'"),
        _db_error(1213 + 1, "something else", OperationalError),
        _db_error(1452, "Cannot add or update a child row"),
    ],
)
def test_other_database_errors_are_not_retried(client, ids, monkeypatch, error):
    calls = _fail_first(monkeypatch, 10**6, error)
    add_to_cart(client, ids["latte"], "M")
    response = client.post("/api/orders", headers=device())
    assert response.status_code == 500
    assert error_of(response)["code"] == "INTERNAL_ERROR"
    assert calls["count"] == 1
