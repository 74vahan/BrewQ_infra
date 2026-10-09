from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TABLE_OPTIONS, Base
from app.db.types import UBigInt, UInt, USmallInt, UtcDateTime, str_enum
from app.domain.sizes import Size


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("customer_id", "menu_item_id", "size", name="uq_cart_items_line"),
        CheckConstraint("qty BETWEEN 1 AND 20", name="ck_cart_items_qty"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(UBigInt, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        UBigInt,
        ForeignKey("customers.id", name="fk_cart_items_customer", ondelete="CASCADE"),
        nullable=False,
    )
    menu_item_id: Mapped[int] = mapped_column(
        UInt,
        ForeignKey("menu_items.id", name="fk_cart_items_menu_item", ondelete="RESTRICT"),
        nullable=False,
    )
    size: Mapped[Size] = mapped_column(
        str_enum(Size, name="ck_cart_items_size", length=1), nullable=False
    )
    qty: Mapped[int] = mapped_column(USmallInt, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
