"""Customer identity (X-Device-Id) and the optional display name."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.db.uow import unit_of_work
from app.domain.device_id import normalize_device_id
from app.models.customer import Customer
from app.repositories import customers as customers_repo


def resolve_customer(session: Session, raw_device_id: str | None, now: datetime) -> Customer:
    """Customer for the X-Device-Id header value; created on the first request (upsert).

    The transaction is ended before returning, so the service call that follows starts
    a fresh one (and a fresh snapshot) after it has taken its own locks.
    """
    if not raw_device_id:
        raise AppError(ErrorCode.DEVICE_ID_MISSING, 400, "X-Device-Id header is required")
    device_id = normalize_device_id(raw_device_id)
    if device_id is None:
        raise AppError(ErrorCode.DEVICE_ID_INVALID, 400, "X-Device-Id must be a UUID v4")

    with unit_of_work(session):
        customer = customers_repo.get_by_device_id(session, device_id)
        if customer is None:
            customers_repo.insert_if_absent(session, device_id, now)
            # Locking read: a concurrent first request may have committed the row
            # after our snapshot was taken.
            customer = customers_repo.get_by_device_id(session, device_id, latest=True)
    assert customer is not None  # the insert above is committed by now
    return customer


def set_name(session: Session, customer_id: int, name: str | None) -> str | None:
    with unit_of_work(session):
        customers_repo.set_name(session, customer_id, name)
    return name
