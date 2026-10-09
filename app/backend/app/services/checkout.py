"""Checkout: the cart becomes an order in one transaction (memory/02-database.md).

Steps of one attempt: lock the customer, refuse a second active order, read the cart,
refuse an empty or unorderable cart (all problem lines at once), allocate the pickup
code, insert order + lines + the creation event, clear the cart, commit.

Two checkouts of different customers can read the same MAX(code); the second insert
hits the unique index uq_orders_day_code (MySQL error 1062) and the whole transaction
is repeated. A deadlock (1213) is repeated the same way.
"""

import logging
import random
import time
from datetime import datetime

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import AppError, ErrorCode
from app.db.uow import unit_of_work
from app.domain.business_day import business_day
from app.domain.order_code import MAX_DAILY_ORDERS, DailyOrderLimitReached, next_code
from app.domain.order_status import OrderStatus
from app.domain.sizes import price_for
from app.models.cart_item import CartItem
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.repositories import cart_items as cart_items_repo
from app.repositories import customers as customers_repo
from app.repositories import order_events as order_events_repo
from app.repositories import order_items as order_items_repo
from app.repositories import orders as orders_repo
from app.services.cart import line_problem
from app.services.order_views import OrderView, build_order_view

log = logging.getLogger(__name__)

# With N concurrent checkouts, one succeeds per round, so the last of N needs up to N
# attempts (measured: ten simultaneous checkouts reach attempt 9). A few milliseconds of
# jitter keeps the retries from colliding in lockstep. One cafe never gets close to 15.
MAX_ATTEMPTS = 15
_MAX_BACKOFF_SECONDS = 0.03

_DUPLICATE_ENTRY = 1062
_DEADLOCK = 1213
_DAY_CODE_INDEX = "uq_orders_day_code"


def checkout(session: Session, customer_id: int, clock: Clock) -> OrderView:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with unit_of_work(session):
                order = _create_order(session, customer_id, clock.now())
            break
        except DBAPIError as exc:
            if not _is_retryable(exc):
                raise
            log.info("Checkout attempt %d/%d lost a race: %s", attempt, MAX_ATTEMPTS, exc.orig)
            if attempt == MAX_ATTEMPTS:
                log.error("Checkout failed after %d attempts", MAX_ATTEMPTS)
                raise AppError(
                    ErrorCode.INTERNAL_ERROR, 500, "Order could not be created, try again"
                ) from exc
            time.sleep(random.uniform(0, _MAX_BACKOFF_SECONDS))  # jitter only, not cryptography
    return build_order_view(session, order)


def _is_retryable(exc: DBAPIError) -> bool:
    args = getattr(exc.orig, "args", ())
    errno = args[0] if args else None
    if errno == _DEADLOCK:
        return True
    return errno == _DUPLICATE_ENTRY and _DAY_CODE_INDEX in str(exc.orig)


def _create_order(session: Session, customer_id: int, now: datetime) -> Order:
    day = business_day(now)
    customers_repo.lock(session, customer_id)

    active = orders_repo.find_active(session, customer_id)
    if active is not None:
        raise AppError(
            ErrorCode.ACTIVE_ORDER_EXISTS,
            409,
            "The customer already has an active order",
            {"order_id": active.id, "code": active.code, "status": active.status.value},
        )

    lines = cart_items_repo.list_lines(session, customer_id, for_update=True)
    if not lines:
        raise AppError(ErrorCode.CART_EMPTY, 409, "The cart is empty")
    _raise_for_problems(lines)

    try:
        code = next_code(orders_repo.max_code_for_day(session, day))
    except DailyOrderLimitReached as exc:
        raise AppError(
            ErrorCode.DAILY_ORDER_LIMIT_REACHED,
            409,
            "The daily order limit is reached",
            {"limit": MAX_DAILY_ORDERS},
        ) from exc

    prices = [(line, price_for(item, line.size) or 0) for line, item in lines]
    total = sum(price * line.qty for line, price in prices)
    order = orders_repo.insert(
        session, code=code, customer_id=customer_id, total_amd=total, now=now
    )
    order_items_repo.add_all(
        session,
        [
            OrderItem(
                order_id=order.id,
                menu_item_id=line.menu_item_id,
                size=line.size,
                qty=line.qty,
                unit_price_amd=price,
            )
            for line, price in prices
        ],
    )
    order_events_repo.add(session, order.id, None, OrderStatus.NEW, now)
    cart_items_repo.clear(session, customer_id)
    return order


def _raise_for_problems(lines: list[tuple[CartItem, MenuItem]]) -> None:
    problems = [
        {
            "cart_item_id": line.id,
            "menu_item_id": item.id,
            "name": item.name,
            "size": line.size.value,
            "reason": reason,
        }
        for line, item in lines
        if (reason := line_problem(item, line.size)) is not None
    ]
    if problems:
        raise AppError(
            ErrorCode.CART_HAS_UNAVAILABLE_ITEMS,
            409,
            "Some cart items cannot be ordered",
            {"items": problems},
        )
