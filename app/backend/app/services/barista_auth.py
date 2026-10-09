"""Barista login and token verification (the primitives live in core/security.py)."""

from datetime import datetime

from app.core import security
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode


def login(settings: Settings, password: str, now: datetime) -> tuple[str, datetime]:
    if not security.check_password(settings, password):
        raise AppError(ErrorCode.BARISTA_INVALID_PASSWORD, 401, "Invalid password")
    return security.issue_token(settings, now)


def authorize(settings: Settings, authorization: str | None, now: datetime) -> None:
    """Accept `Authorization: Bearer <token>`; anything else is 401 BARISTA_UNAUTHORIZED."""
    token = _bearer_token(authorization)
    if token is None or not security.verify_token(settings, token, now):
        raise AppError(ErrorCode.BARISTA_UNAUTHORIZED, 401, "Barista authentication required")


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or " " in token:
        return None
    return token
