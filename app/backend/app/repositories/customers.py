from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.customer import Customer


def get_by_device_id(session: Session, device_id: str, *, latest: bool = False) -> Customer | None:
    """`latest=True` is a locking read: it also sees rows committed after our snapshot."""
    statement = select(Customer).where(Customer.device_id == device_id)
    if latest:
        statement = statement.with_for_update(read=True)
    return session.scalar(statement)


def get(session: Session, customer_id: int) -> Customer | None:
    return session.get(Customer, customer_id)


def insert_if_absent(session: Session, device_id: str, now: datetime) -> None:
    """Create the customer unless one exists; safe when two first requests race.

    `id = LAST_INSERT_ID(id)` turns the duplicate-key branch into a no-op update.
    """
    statement = (
        mysql_insert(Customer)
        .values(device_id=device_id, created_at=now)
        .on_duplicate_key_update(id=func.last_insert_id(Customer.id))
    )
    session.execute(statement)


def lock(session: Session, customer_id: int) -> None:
    """Row lock that serializes cart changes and checkout of one customer."""
    session.execute(select(Customer.id).where(Customer.id == customer_id).with_for_update())


def set_name(session: Session, customer_id: int, name: str | None) -> None:
    session.execute(update(Customer).where(Customer.id == customer_id).values(name=name))
