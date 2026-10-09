from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TABLE_OPTIONS, Base
from app.db.types import UBigInt, UtcDateTime


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("device_id", name="uq_customers_device_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(UBigInt, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(mysql.CHAR(36, charset="ascii"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(40), nullable=True, server_default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
