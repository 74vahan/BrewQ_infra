from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TABLE_OPTIONS, Base
from app.db.types import CodeChar, UBigInt, UInt, UtcDateTime, str_enum
from app.domain.order_status import OrderStatus


class Order(Base):
    """Customer order.

    The functional unique index uq_orders_day_code
    (UNIQUE ((DATE(created_at + INTERVAL 4 HOUR)), code)) is created by raw DDL in
    migration 0001 and is deliberately NOT declared here: Alembic autogenerate does
    not understand functional indexes (it is excluded in alembic/env.py).
    """

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("code REGEXP '^A-[0-9]{3}$' AND code <> 'A-000'", name="ck_orders_code"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(UBigInt, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(CodeChar, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        UBigInt,
        ForeignKey("customers.id", name="fk_orders_customer", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, name="ck_orders_status", length=16),
        nullable=False,
        server_default=OrderStatus.NEW.value,
    )
    total_amd: Mapped[int] = mapped_column(UInt, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
