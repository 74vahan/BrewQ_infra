from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TABLE_OPTIONS, Base
from app.db.types import UBigInt, UInt, USmallInt, str_enum
from app.domain.sizes import Size


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "menu_item_id", "size", name="uq_order_items_line"),
        CheckConstraint("qty BETWEEN 1 AND 20", name="ck_order_items_qty"),
        CheckConstraint("unit_price_amd > 0", name="ck_order_items_price"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(UBigInt, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        UBigInt,
        ForeignKey("orders.id", name="fk_order_items_order", ondelete="RESTRICT"),
        nullable=False,
    )
    menu_item_id: Mapped[int] = mapped_column(
        UInt,
        ForeignKey("menu_items.id", name="fk_order_items_menu_item", ondelete="RESTRICT"),
        nullable=False,
    )
    size: Mapped[Size] = mapped_column(
        str_enum(Size, name="ck_order_items_size", length=1), nullable=False
    )
    qty: Mapped[int] = mapped_column(USmallInt, nullable=False)
    unit_price_amd: Mapped[int] = mapped_column(UInt, nullable=False)
