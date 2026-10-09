"""JWT/password primitives of the barista authentication (no database)."""

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr

from app.core import security
from app.core.config import Settings
from app.services.barista_auth import _bearer_token

NOW = datetime(2026, 10, 9, 8, 0, 0, 123456, tzinfo=UTC)
PASSWORD = "pw-" + secrets.token_hex(6)
SECRET = secrets.token_hex(32)


def make_settings(password: str = PASSWORD, secret: str = SECRET, ttl: int = 12) -> Settings:
    return Settings(
        _env_file=None,
        database_url="mysql+pymysql://u:p@127.0.0.1:1/x",
        barista_password=SecretStr(password),
        barista_token_secret=SecretStr(secret),
        barista_token_ttl_hours=ttl,
    )


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


# --- password ----------------------------------------------------------------------------------


def test_correct_password_matches_and_wrong_ones_do_not():
    settings = make_settings()
    assert security.check_password(settings, PASSWORD)
    assert not security.check_password(settings, PASSWORD + "x")
    assert not security.check_password(settings, PASSWORD.upper())
    assert not security.check_password(settings, "")


def test_empty_configured_password_never_matches_anything():
    settings = make_settings(password="", secret="")
    assert not security.barista_enabled(settings)
    assert not security.check_password(settings, "")
    assert not security.check_password(settings, "anything")


def test_non_ascii_passwords_work_and_do_not_crash():
    armenian = "".join(chr(c) for c in (0x531, 0x576, 0x56B, 0x20, 0x418, 0x432))
    settings = make_settings(password=armenian)
    assert security.check_password(settings, armenian)
    assert not security.check_password(settings, armenian + "!")
    assert not security.check_password(make_settings(), armenian)  # candidate is non-ASCII


def test_password_version_depends_on_secret_and_password_and_hides_both():
    base = security.password_version(make_settings())
    assert len(base) == 16
    int(base, 16)  # hex
    assert PASSWORD not in base
    assert security.password_version(make_settings(password=PASSWORD + "1")) != base
    assert security.password_version(make_settings(secret=secrets.token_hex(32))) != base
    assert security.password_version(make_settings()) == base


# --- tokens ------------------------------------------------------------------------------------


def test_issued_token_verifies_and_carries_the_documented_claims():
    settings = make_settings()
    token, expires_at = security.issue_token(settings, NOW)
    assert security.verify_token(settings, token, NOW)
    claims = jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert set(claims) == {"sub", "iat", "exp", "pwv"}
    assert claims["sub"] == "barista"
    assert claims["iat"] == int(NOW.replace(microsecond=0).timestamp())
    assert claims["exp"] - claims["iat"] == 12 * 3600
    assert claims["pwv"] == security.password_version(settings)
    assert expires_at == NOW.replace(microsecond=0) + timedelta(hours=12)
    assert PASSWORD not in token


def test_ttl_follows_the_setting():
    token, expires_at = security.issue_token(make_settings(ttl=3), NOW)
    assert expires_at == NOW.replace(microsecond=0) + timedelta(hours=3)
    assert security.verify_token(make_settings(ttl=3), token, NOW + timedelta(hours=2, minutes=59))
    assert not security.verify_token(
        make_settings(ttl=3), token, NOW + timedelta(hours=3, seconds=1)
    )


def test_token_expires_exactly_at_exp():
    settings = make_settings()
    token, expires_at = security.issue_token(settings, NOW)
    assert security.verify_token(settings, token, expires_at - timedelta(microseconds=1))
    assert not security.verify_token(settings, token, expires_at)
    assert not security.verify_token(settings, token, expires_at + timedelta(days=1))


def test_token_signed_with_another_key_is_rejected():
    other = make_settings(secret=secrets.token_hex(32))
    token, _ = security.issue_token(other, NOW)
    assert not security.verify_token(make_settings(), token, NOW)


def test_token_for_an_old_password_is_rejected():
    token, _ = security.issue_token(make_settings(), NOW)
    assert not security.verify_token(make_settings(password=PASSWORD + "-new"), token, NOW)


def test_tampered_payload_is_rejected():
    token, _ = security.issue_token(make_settings(), NOW)
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["exp"] += 10**6
    assert not security.verify_token(
        make_settings(), ".".join([header, _b64(claims), signature]), NOW
    )


def test_alg_none_token_is_rejected():
    claims = {
        "sub": "barista",
        "iat": 0,
        "exp": 4_000_000_000,
        "pwv": security.password_version(make_settings()),
    }
    forged = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."
    assert not security.verify_token(make_settings(), forged, NOW)


def test_other_hmac_algorithms_are_rejected():
    settings = make_settings()
    claims = {
        "sub": "barista",
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + 3600,
        "pwv": security.password_version(settings),
    }
    for algorithm in ("HS384", "HS512"):
        assert not security.verify_token(settings, jwt.encode(claims, SECRET, algorithm), NOW)
    assert security.verify_token(settings, jwt.encode(claims, SECRET, "HS256"), NOW)


def _signed(**overrides) -> str:
    settings = make_settings()
    claims = {
        "sub": "barista",
        "iat": int(NOW.timestamp()),
        "exp": int(NOW.timestamp()) + 3600,
        "pwv": security.password_version(settings),
        **overrides,
    }
    claims = {key: value for key, value in claims.items() if value is not ...}
    return jwt.encode(claims, SECRET, "HS256")


def test_the_helper_makes_a_valid_token():
    assert security.verify_token(make_settings(), _signed(), NOW)


@pytest.mark.parametrize("missing", ["sub", "iat", "exp", "pwv"])
def test_missing_claims_are_rejected(missing):
    assert not security.verify_token(make_settings(), _signed(**{missing: ...}), NOW)


@pytest.mark.parametrize(
    "overrides",
    [
        {"sub": "admin"},
        {"sub": 1},
        {"pwv": 123},
        {"pwv": "0" * 16},
        {"exp": "soon"},
        {"exp": True},
        {"iat": None},
        {"exp": 1.5e9 + 0.5},
    ],
)
def test_malformed_claims_are_rejected(overrides):
    assert not security.verify_token(make_settings(), _signed(**overrides), NOW)


@pytest.mark.parametrize(
    "garbage",
    ["", "abc", "a.b.c", "....", "Bearer x", "é.é.é", "x" * 10_000, "a.b"],
)
def test_garbage_is_rejected_without_raising(garbage):
    assert not security.verify_token(make_settings(), garbage, NOW)


def test_nothing_verifies_when_barista_access_is_not_configured():
    token, _ = security.issue_token(make_settings(), NOW)
    assert not security.verify_token(make_settings(password="", secret=""), token, NOW)


# --- Authorization header ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "token"),
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer abc", "abc"),
        ("BEARER abc", "abc"),
        ("Bearer   abc  ", "abc"),
    ],
)
def test_bearer_header_is_parsed(header, token):
    assert _bearer_token(header) == token


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer", "Bearer ", "Basic abc", "abc", "Token abc", "Bearer a b", "Bearerabc"],
)
def test_other_authorization_headers_give_no_token(header):
    assert _bearer_token(header) is None
