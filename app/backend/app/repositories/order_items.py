from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.models.order_item import OrderItem


def add_all(session: Session, items: list[OrderItem]) -> None:
    session.add_all(items)
    session.flush()


def list_for_orders(
    session: Session, order_ids: Collection[int]
) -> list[tuple[OrderItem, MenuItem]]:
    """Lines of the given orders with their menu items, ordered by line id."""
    if not order_ids:
        return []
    statement = (
        select(OrderItem, MenuItem)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .where(OrderItem.order_id.in_(order_ids))
        .order_by(OrderItem.id)
    )
    return [(line, item) for line, item in session.execute(statement)]
