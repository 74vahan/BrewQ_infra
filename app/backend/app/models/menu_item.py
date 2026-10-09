from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TABLE_OPTIONS, Base
from app.db.types import UInt, str_enum
from app.domain.categories import Category


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint("name", name="uq_menu_items_name"),
        CheckConstraint(
            "price_m > 0 AND (price_s IS NULL OR price_s > 0) AND (price_l IS NULL OR price_l > 0)",
            name="ck_menu_items_prices",
        ),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Category] = mapped_column(
        str_enum(Category, name="ck_menu_items_category", length=16), nullable=False
    )
    price_s: Mapped[int | None] = mapped_column(UInt, nullable=True)
    price_m: Mapped[int] = mapped_column(UInt, nullable=False)
    price_l: Mapped[int | None] = mapped_column(UInt, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
