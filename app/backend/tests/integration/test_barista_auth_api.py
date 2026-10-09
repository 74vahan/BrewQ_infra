"""POST /api/barista/login and the guard in front of every other /api/barista/* route."""

import base64
import json
import secrets
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core import security
from app.core.config import Settings
from app.main import create_app
from tests.integration.api_helpers import (
    BARISTA_PASSWORD,
    BARISTA_TOKEN_SECRET,
    DEVICE_A,
    TIMESTAMP_RE,
    barista_login,
    device,
    error_of,
)
from tests.integration.conftest import TEST_DATABASE_URL

PROTECTED = [
    ("GET", "/api/barista/orders"),
    ("GET", "/api/barista/orders?scope=today"),
    ("POST", "/api/barista/orders/1/status"),
    ("GET", "/api/barista/menu"),
    ("PATCH", "/api/barista/menu/1"),
]
BODIES = {"POST": {"to": "IN_PROGRESS"}, "PATCH": {"is_available": False}}


def _call(client, method, path, headers=None):
    return client.request(method, path, json=BODIES.get(method), headers=headers or {})


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "database_url": TEST_DATABASE_URL,
        "barista_password": SecretStr(BARISTA_PASSWORD),
        "barista_token_secret": SecretStr(BARISTA_TOKEN_SECRET),
        **overrides,
    }
    return Settings(**values)


# --- login ---------------------------------------------------------------------------------


def test_login_returns_a_token_and_its_expiry(client, clock):
    response = client.post("/api/barista/login", json={"password": BARISTA_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"token", "expires_at"}
    assert TIMESTAMP_RE.match(body["expires_at"])
    assert body["expires_at"] == "2026-10-09T20:00:00.000000Z"  # 08:00 + 12 h
    claims = jwt.decode(
        body["token"],
        BARISTA_TOKEN_SECRET,
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert claims["sub"] == "barista"
    assert BARISTA_PASSWORD not in body["token"]


def test_token_lifetime_follows_the_configured_ttl(app, clock):
    with TestClient(create_app(_settings(barista_token_ttl_hours=2))) as other:
        other.app.dependency_overrides.update(app.dependency_overrides)
        body = other.post("/api/barista/login", json={"password": BARISTA_PASSWORD}).json()
    assert body["expires_at"] == "2026-10-09T10:00:00.000000Z"


@pytest.mark.parametrize(
    "password", ["", " ", "wrong", BARISTA_PASSWORD + " ", BARISTA_PASSWORD.upper()]
)
def test_wrong_password_is_401(client, password):
    response = client.post("/api/barista/login", json={"password": password})
    assert response.status_code == 401
    error = error_of(response)
    assert error["code"] == "BARISTA_INVALID_PASSWORD"
    assert error["details"] == {}
    assert "token" not in response.text


def test_login_does_not_need_a_device_id(client):
    assert client.post("/api/barista/login", json={"password": BARISTA_PASSWORD}).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"password": None},
        {"password": 123},
        {"password": "x", "extra": 1},
        [],
        {"password": "x" * 1025},
    ],
)
def test_login_validates_the_body(client, body):
    response = client.post("/api/barista/login", json=body)
    assert response.status_code == 400
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_login_with_a_non_ascii_password(clock):
    armenian = "".join(chr(c) for c in (0x531, 0x576, 0x56B, 0x20, 0x418, 0x432, 0x430, 0x43D))
    app = create_app(_settings(barista_password=SecretStr(armenian)))
    from app.api.deps import get_clock

    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app, raise_server_exceptions=False) as client:
        ok = client.post("/api/barista/login", json={"password": armenian})
        bad = client.post("/api/barista/login", json={"password": armenian + "!"})
    assert ok.status_code == 200
    assert error_of(bad)["code"] == "BARISTA_INVALID_PASSWORD"


def test_unconfigured_barista_password_locks_everyone_out(clock):
    from app.api.deps import get_clock

    app = create_app(_settings(barista_password=SecretStr(""), barista_token_secret=SecretStr("")))
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app, raise_server_exceptions=False) as client:
        for password in ("", "anything"):
            response = client.post("/api/barista/login", json={"password": password})
            assert error_of(response)["code"] == "BARISTA_INVALID_PASSWORD"
        # a token signed with an arbitrary secret does not open the door either
        forged = jwt.encode(
            {"sub": "barista", "iat": 0, "exp": 4_000_000_000, "pwv": "0" * 16}, "x" * 40, "HS256"
        )
        response = client.get("/api/barista/orders", headers={"Authorization": f"Bearer {forged}"})
        assert error_of(response)["code"] == "BARISTA_UNAUTHORIZED"


# --- the guard -------------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_a_valid_token_opens_every_barista_route(client, method, path):
    headers = barista_login(client)
    response = _call(client, method, path, headers)
    assert response.status_code in {200, 404}, response.text  # 404 = no such order/item
    if response.status_code == 404:
        assert error_of(response)["code"] in {"ORDER_NOT_FOUND", "MENU_ITEM_NOT_FOUND"}


def _bad_header_cases(clock):
    """(label, Authorization header value or None)."""
    settings = _settings()
    now = clock.now()
    good, _ = security.issue_token(settings, now)
    other_secret, _ = security.issue_token(
        _settings(barista_token_secret=SecretStr(secrets.token_hex(32))), now
    )
    old_password, _ = security.issue_token(_settings(barista_password=SecretStr("old-pw")), now)
    expired, _ = security.issue_token(settings, now - timedelta(hours=13))
    pwv = security.password_version(settings)
    claims = {"sub": "barista", "iat": 0, "exp": 4_000_000_000, "pwv": pwv}
    alg_none = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."
    wrong_sub = jwt.encode({**claims, "sub": "admin"}, BARISTA_TOKEN_SECRET, "HS256")
    no_pwv = jwt.encode(
        {key: value for key, value in claims.items() if key != "pwv"}, BARISTA_TOKEN_SECRET, "HS256"
    )
    no_exp = jwt.encode(
        {key: value for key, value in claims.items() if key != "exp"}, BARISTA_TOKEN_SECRET, "HS256"
    )
    head, payload, signature = good.split(".")
    flipped = signature[:-2] + ("AA" if not signature.endswith("AA") else "BB")
    return [
        ("no header", None),
        ("empty header", ""),
        ("scheme only", "Bearer"),
        ("empty token", "Bearer "),
        ("basic scheme", f"Basic {good}"),
        ("raw token without scheme", good),
        ("garbage", "Bearer not-a-token"),
        ("three dots", "Bearer a.b.c"),
        ("two tokens", f"Bearer {good} {good}"),
        ("signed with another key", f"Bearer {other_secret}"),
        ("stale password version", f"Bearer {old_password}"),
        ("expired", f"Bearer {expired}"),
        ("alg none", f"Bearer {alg_none}"),
        ("wrong subject", f"Bearer {wrong_sub}"),
        ("missing pwv", f"Bearer {no_pwv}"),
        ("missing exp", f"Bearer {no_exp}"),
        ("flipped signature", f"Bearer {head}.{payload}.{flipped}"),
        ("password as token", f"Bearer {BARISTA_PASSWORD}"),
    ]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_kind_of_bad_token_is_401_on_every_barista_route(client, clock, method, path):
    for label, value in _bad_header_cases(clock):
        headers = {} if value is None else {"Authorization": value}
        response = _call(client, method, path, headers)
        assert response.status_code == 401, label
        error = error_of(response)
        assert error["code"] == "BARISTA_UNAUTHORIZED", label
        assert error["details"] == {}, label


def test_the_control_case_the_good_token_from_the_same_generator_works(client, clock):
    good, _ = security.issue_token(_settings(), clock.now())
    response = client.get("/api/barista/orders", headers={"Authorization": f"Bearer {good}"})
    assert response.status_code == 200


def test_the_token_works_until_it_expires_and_not_after(client, clock):
    headers = barista_login(client)
    clock.advance(hours=11, minutes=59)
    assert client.get("/api/barista/orders", headers=headers).status_code == 200
    clock.advance(minutes=1)
    response = client.get("/api/barista/orders", headers=headers)
    assert response.status_code == 401
    assert error_of(response)["code"] == "BARISTA_UNAUTHORIZED"


def test_changing_the_password_invalidates_issued_tokens(client, clock):
    headers = barista_login(client)
    app = create_app(_settings(barista_password=SecretStr(BARISTA_PASSWORD + "-rotated")))
    from app.api.deps import get_clock

    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app, raise_server_exceptions=False) as restarted:
        response = restarted.get("/api/barista/orders", headers=headers)
    assert response.status_code == 401
    assert error_of(response)["code"] == "BARISTA_UNAUTHORIZED"


def test_auth_is_checked_before_the_body(client):
    response = client.post("/api/barista/orders/1/status", json={"to": "nonsense"})
    assert response.status_code == 401


def test_a_device_id_is_not_a_credential(client):
    for method, path in PROTECTED:
        response = _call(client, method, path, device(DEVICE_A))
        assert response.status_code == 401


def test_the_barista_token_does_not_replace_the_device_id(client):
    headers = barista_login(client)
    response = client.get("/api/menu", headers=headers)
    assert response.status_code == 400
    assert error_of(response)["code"] == "DEVICE_ID_MISSING"
