from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem


def get_by_name(session: Session, name: str) -> MenuItem | None:
    # `name` is unique under a case-insensitive collation, so this match is too.
    return session.scalar(select(MenuItem).where(MenuItem.name == name))


def get(session: Session, menu_item_id: int) -> MenuItem | None:
    return session.get(MenuItem, menu_item_id)


def list_all(session: Session) -> list[MenuItem]:
    return list(session.scalars(select(MenuItem).order_by(MenuItem.id)))
