from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.sizes import Size
from app.models.cart_item import CartItem
from app.models.menu_item import MenuItem


def list_lines(
    session: Session, customer_id: int, *, for_update: bool = False
) -> list[tuple[CartItem, MenuItem]]:
    """Cart lines of the customer with their menu items, ordered by line id."""
    statement = (
        select(CartItem, MenuItem)
        .join(MenuItem, MenuItem.id == CartItem.menu_item_id)
        .where(CartItem.customer_id == customer_id)
        .order_by(CartItem.id)
    )
    if for_update:
        statement = statement.with_for_update(of=CartItem)
    return [(line, item) for line, item in session.execute(statement)]


def find_line(session: Session, customer_id: int, menu_item_id: int, size: Size) -> CartItem | None:
    # Locking read: sees the latest committed state, not an older snapshot.
    return session.scalar(
        select(CartItem)
        .where(
            CartItem.customer_id == customer_id,
            CartItem.menu_item_id == menu_item_id,
            CartItem.size == size,
        )
        .with_for_update()
    )


def get_own(session: Session, customer_id: int, cart_item_id: int) -> CartItem | None:
    """A cart line of this customer; a foreign or missing id gives None."""
    return session.scalar(
        select(CartItem)
        .where(CartItem.id == cart_item_id, CartItem.customer_id == customer_id)
        .with_for_update()
    )


def add_line(
    session: Session, customer_id: int, menu_item_id: int, size: Size, qty: int, now: datetime
) -> CartItem:
    line = CartItem(
        customer_id=customer_id, menu_item_id=menu_item_id, size=size, qty=qty, updated_at=now
    )
    session.add(line)
    session.flush()
    return line


def set_qty(session: Session, line: CartItem, qty: int, now: datetime) -> None:
    line.qty = qty
    line.updated_at = now
    session.flush()


def delete_line(session: Session, line: CartItem) -> None:
    session.delete(line)
    session.flush()


def clear(session: Session, customer_id: int) -> None:
    session.execute(delete(CartItem).where(CartItem.customer_id == customer_id))
