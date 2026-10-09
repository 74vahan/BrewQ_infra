"""Barista side of orders: the queue, today's list and status changes."""

from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.db.uow import unit_of_work
from app.domain.business_day import business_day
from app.domain.order_status import Actor, OrderStatus, allowed_targets, can_transition
from app.repositories import orders as orders_repo
from app.services.errors import order_not_found
from app.services.order_transitions import apply_transition
from app.services.order_views import OrderView, build_order_view, build_order_views

Scope = Literal["active", "today"]


def list_orders(session: Session, scope: Scope, now: datetime) -> list[OrderView]:
    """`active`: the queue, oldest first. `today`: the current Yerevan day, newest first."""
    if scope == "active":
        orders = orders_repo.list_active(session)
    else:
        orders = orders_repo.list_for_day(session, business_day(now))
    return build_order_views(session, orders)


def change_status(session: Session, order_id: int, target: OrderStatus, now: datetime) -> OrderView:
    """Move an order one allowed step. Whoever loses a race gets 409, never a double step."""
    with unit_of_work(session):
        order = orders_repo.get(session, order_id)
        if order is None:
            raise order_not_found(order_id)
        if not can_transition(order.status, target, Actor.BARISTA):
            raise _invalid_transition(order.status, target)
        if not apply_transition(session, order_id, order.status, target, now):
            # Someone (usually the client cancelling) changed the order first.
            current = orders_repo.read_status(session, order_id) or order.status
            raise _invalid_transition(current, target)
    session.refresh(order)
    return build_order_view(session, order)


def _invalid_transition(current: OrderStatus, target: OrderStatus) -> AppError:
    return AppError(
        ErrorCode.INVALID_STATUS_TRANSITION,
        409,
        "This status change is not allowed",
        {
            "from": current.value,
            "to": target.value,
            "allowed": [status.value for status in allowed_targets(current, Actor.BARISTA)],
        },
    )
