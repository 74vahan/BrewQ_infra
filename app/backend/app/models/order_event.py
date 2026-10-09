from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TABLE_OPTIONS, Base
from app.db.types import UBigInt, UtcDateTime, str_enum
from app.domain.order_status import OrderStatus


class OrderEvent(Base):
    __tablename__ = "order_events"
    __table_args__ = (
        Index("ix_order_events_order", "order_id", "created_at"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(UBigInt, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        UBigInt,
        ForeignKey("orders.id", name="fk_order_events_order", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(
        str_enum(OrderStatus, name="ck_order_events_from_status", length=16), nullable=True
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, name="ck_order_events_to_status", length=16), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
