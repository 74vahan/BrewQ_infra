"""Server-side cart: reading with current prices and the cart mutations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.db.uow import unit_of_work
from app.domain.cart import MAX_LINE_QTY
from app.domain.sizes import Size, offered_sizes, price_for
from app.models.cart_item import CartItem
from app.models.menu_item import MenuItem
from app.repositories import cart_items as cart_items_repo
from app.repositories import customers as customers_repo
from app.repositories import menu_items as menu_items_repo
from app.services.errors import cart_item_not_found, menu_item_not_found

Problem = Literal["unavailable", "size_not_offered"]


@dataclass(frozen=True)
class CartLineView:
    id: int
    menu_item_id: int
    name: str
    image_url: str | None
    size: Size
    qty: int
    unit_price_amd: int | None  # None only when the size is no longer offered
    line_total_amd: int | None
    is_available: bool
    problem: Problem | None


@dataclass(frozen=True)
class CartView:
    items: list[CartLineView]
    total_amd: int
    can_checkout: bool


def line_problem(item: MenuItem, size: Size) -> Problem | None:
    """Why this cart line cannot be ordered (the stop-list wins over a missing price)."""
    if not item.is_available:
        return "unavailable"
    if price_for(item, size) is None:
        return "size_not_offered"
    return None


def _line_view(line: CartItem, item: MenuItem) -> CartLineView:
    unit_price = price_for(item, line.size)
    return CartLineView(
        id=line.id,
        menu_item_id=item.id,
        name=item.name,
        image_url=item.image_url,
        size=line.size,
        qty=line.qty,
        unit_price_amd=unit_price,
        line_total_amd=None if unit_price is None else unit_price * line.qty,
        is_available=item.is_available,
        problem=line_problem(item, line.size),
    )


def get_cart(session: Session, customer_id: int) -> CartView:
    views = [
        _line_view(line, item) for line, item in cart_items_repo.list_lines(session, customer_id)
    ]
    # Lines with a problem are not payable, so they stay out of the total.
    total = sum(view.line_total_amd or 0 for view in views if view.problem is None)
    return CartView(
        items=views,
        total_amd=total,
        can_checkout=bool(views) and all(view.problem is None for view in views),
    )


def add_item(
    session: Session,
    customer_id: int,
    menu_item_id: int,
    size: Size,
    qty: int,
    now: datetime,
) -> CartView:
    item = menu_items_repo.get(session, menu_item_id)
    if item is None:
        raise menu_item_not_found(menu_item_id)
    if not item.is_available:
        raise AppError(
            ErrorCode.MENU_ITEM_UNAVAILABLE,
            409,
            "Menu item is unavailable",
            {"menu_item_id": menu_item_id},
        )
    if price_for(item, size) is None:
        raise AppError(
            ErrorCode.SIZE_NOT_OFFERED,
            400,
            "This size is not offered for the item",
            {
                "menu_item_id": menu_item_id,
                "size": size.value,
                "offered": [offered.value for offered in offered_sizes(item)],
            },
        )

    with unit_of_work(session):
        # The customer row lock serializes this customer's cart changes (and checkout),
        # so the read-then-write below cannot interleave with another request.
        customers_repo.lock(session, customer_id)
        line = cart_items_repo.find_line(session, customer_id, menu_item_id, size)
        if line is None:
            cart_items_repo.add_line(session, customer_id, menu_item_id, size, qty, now)
        else:
            if line.qty + qty > MAX_LINE_QTY:
                raise AppError(
                    ErrorCode.CART_QTY_LIMIT_EXCEEDED,
                    409,
                    "Cart line quantity limit exceeded",
                    {"max": MAX_LINE_QTY, "current": line.qty},
                )
            cart_items_repo.set_qty(session, line, line.qty + qty, now)
    return get_cart(session, customer_id)


def set_qty(
    session: Session, customer_id: int, cart_item_id: int, qty: int, now: datetime
) -> CartView:
    with unit_of_work(session):
        customers_repo.lock(session, customer_id)
        line = cart_items_repo.get_own(session, customer_id, cart_item_id)
        if line is None:
            raise cart_item_not_found(cart_item_id)
        cart_items_repo.set_qty(session, line, qty, now)
    return get_cart(session, customer_id)


def remove_item(session: Session, customer_id: int, cart_item_id: int) -> CartView:
    with unit_of_work(session):
        customers_repo.lock(session, customer_id)
        line = cart_items_repo.get_own(session, customer_id, cart_item_id)
        if line is None:
            raise cart_item_not_found(cart_item_id)
        cart_items_repo.delete_line(session, line)
    return get_cart(session, customer_id)


def clear_cart(session: Session, customer_id: int) -> CartView:
    with unit_of_work(session):
        customers_repo.lock(session, customer_id)
        cart_items_repo.clear(session, customer_id)
    return get_cart(session, customer_id)
