"""Barista authentication: one shared password -> a signed, expiring JWT (memory/03-api.md).

Token claims: sub="barista", iat, exp, pwv. `pwv` is the first 16 hex characters of
HMAC-SHA256(BARISTA_TOKEN_SECRET, BARISTA_PASSWORD): changing the password in .env and
restarting the api invalidates every issued token, while neither the password nor a
plain hash of it ever appears in a token. Expiry is checked against our Clock (not the
library's wall clock) so tests can move time.
"""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import Settings

ALGORITHM = "HS256"
SUBJECT = "barista"
_PWV_LENGTH = 16


def barista_enabled(settings: Settings) -> bool:
    """Barista access exists only when both the password and the token secret are set."""
    return bool(
        settings.barista_password.get_secret_value()
        and settings.barista_token_secret.get_secret_value()
    )


def check_password(settings: Settings, candidate: str) -> bool:
    """Constant-time comparison; an unconfigured (empty) password never matches."""
    if not barista_enabled(settings):
        return False
    expected = settings.barista_password.get_secret_value().encode("utf-8")
    # compare_digest on bytes: str with non-ASCII characters would raise TypeError.
    return hmac.compare_digest(candidate.encode("utf-8"), expected)


def password_version(settings: Settings) -> str:
    digest = hmac.new(
        settings.barista_token_secret.get_secret_value().encode("utf-8"),
        settings.barista_password.get_secret_value().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:_PWV_LENGTH]


def issue_token(settings: Settings, now: datetime) -> tuple[str, datetime]:
    """(token, expires_at). Timestamps have whole-second precision, as JWT requires."""
    issued_at = now.astimezone(UTC).replace(microsecond=0)
    expires_at = issued_at + timedelta(hours=settings.barista_token_ttl_hours)
    claims = {
        "sub": SUBJECT,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "pwv": password_version(settings),
    }
    token = jwt.encode(claims, settings.barista_token_secret.get_secret_value(), ALGORITHM)
    return token, expires_at


def verify_token(settings: Settings, token: str, now: datetime) -> bool:
    """True only for a token we signed, for the current password, that has not expired."""
    if not barista_enabled(settings):
        return False
    try:
        claims = jwt.decode(
            token,
            settings.barista_token_secret.get_secret_value(),
            algorithms=[ALGORITHM],  # pins HS256: "none" and asymmetric algorithms are refused
            options={
                "require": ["exp", "iat", "sub", "pwv"],
                "verify_exp": False,  # checked below against the application Clock
                "verify_iat": False,
            },
        )
    except (jwt.PyJWTError, ValueError):
        return False

    exp, iat, pwv = claims.get("exp"), claims.get("iat"), claims.get("pwv")
    if claims.get("sub") != SUBJECT or not isinstance(pwv, str):
        return False
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in (exp, iat)):
        return False
    if not hmac.compare_digest(pwv.encode("utf-8"), password_version(settings).encode("utf-8")):
        return False
    return now.timestamp() < exp
