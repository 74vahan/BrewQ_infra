"""The single place where an order changes status.

Compare-and-set (`UPDATE ... WHERE status = :expected`) decides every race: when a
client cancels while the barista starts the order, exactly one UPDATE matches a row.
The audit event is written in the same transaction as the status change.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.order_status import OrderStatus
from app.repositories import order_events as order_events_repo
from app.repositories import orders as orders_repo


def apply_transition(
    session: Session,
    order_id: int,
    expected: OrderStatus,
    target: OrderStatus,
    now: datetime,
) -> bool:
    """Move the order `expected -> target` and record the event.

    Returns False when the order is no longer in `expected` (somebody else changed it
    first); nothing is written then. The caller owns the transaction.
    """
    if not orders_repo.compare_and_set_status(session, order_id, expected, target, now):
        return False
    order_events_repo.add(session, order_id, expected, target, now)
    return True
