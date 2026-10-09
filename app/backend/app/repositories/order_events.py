from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.order_status import OrderStatus
from app.models.order_event import OrderEvent


def add(
    session: Session,
    order_id: int,
    from_status: OrderStatus | None,
    to_status: OrderStatus,
    now: datetime,
) -> None:
    session.add(
        OrderEvent(order_id=order_id, from_status=from_status, to_status=to_status, created_at=now)
    )
    session.flush()
