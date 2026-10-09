"""FastAPI dependencies: db session, clock, settings, the calling customer, the barista."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import Settings
from app.models.customer import Customer
from app.services import barista_auth
from app.services import customer as customer_service


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_clock() -> Clock:
    return SystemClock()


def get_customer(
    db: Annotated[Session, Depends(get_db)],
    clock: Annotated[Clock, Depends(get_clock)],
    x_device_id: Annotated[str | None, Header()] = None,
) -> Customer:
    """The calling customer, from X-Device-Id; created on the first request."""
    return customer_service.resolve_customer(db, x_device_id, clock.now())


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_barista(
    settings: Annotated[Settings, Depends(get_app_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Guard of every /api/barista/* route except login: a valid Bearer token or 401."""
    barista_auth.authorize(settings, authorization, clock.now())
