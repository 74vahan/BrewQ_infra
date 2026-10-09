"""Client-side order reads and cancellation."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.uow import unit_of_work
from app.domain.order_status import Actor, OrderStatus, can_transition
from app.repositories import orders as orders_repo
from app.services.errors import order_not_cancellable, order_not_found
from app.services.order_transitions import apply_transition
from app.services.order_views import OrderView, build_order_view, build_order_views

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


@dataclass(frozen=True)
class OrderPage:
    items: list[OrderView]
    next_before_id: int | None


def current_order(session: Session, customer_id: int) -> OrderView | None:
    order = orders_repo.find_active(session, customer_id)
    return None if order is None else build_order_view(session, order)


def get_order(session: Session, customer_id: int, order_id: int) -> OrderView:
    # A foreign order is reported exactly like a missing one (memory/06-decisions.md, B10).
    order = orders_repo.get_own(session, customer_id, order_id)
    if order is None:
        raise order_not_found(order_id)
    return build_order_view(session, order)


def list_orders(
    session: Session, customer_id: int, *, limit: int, before_id: int | None
) -> OrderPage:
    """Newest first. `next_before_id` is the id to pass as before_id for the next page."""
    # One extra row tells whether another page exists without a COUNT.
    rows = orders_repo.list_for_customer(session, customer_id, limit=limit + 1, before_id=before_id)
    page = rows[:limit]
    next_before_id = page[-1].id if len(rows) > limit else None
    return OrderPage(items=build_order_views(session, page), next_before_id=next_before_id)


def cancel_order(session: Session, customer_id: int, order_id: int, now: datetime) -> OrderView:
    """Client cancellation: only from NEW; the race with the barista is decided by CAS."""
    with unit_of_work(session):
        order = orders_repo.get_own(session, customer_id, order_id)
        if order is None:
            raise order_not_found(order_id)
        if not can_transition(order.status, OrderStatus.CANCELLED, Actor.CLIENT):
            raise order_not_cancellable(order.status)
        if not apply_transition(session, order_id, order.status, OrderStatus.CANCELLED, now):
            # The barista got there first; report the status that won.
            current = orders_repo.read_status(session, order_id)
            raise order_not_cancellable(current or order.status)
    session.refresh(order)
    return build_order_view(session, order)
