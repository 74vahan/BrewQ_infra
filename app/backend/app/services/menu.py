"""Menu reads. The stop-list flag is_available is part of the answer, not a filter."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.uow import unit_of_work
from app.domain.categories import CATEGORY_ORDER, Category
from app.domain.sizes import Size, offered_sizes, price_for
from app.models.menu_item import MenuItem
from app.repositories import menu_items as menu_items_repo
from app.services.errors import menu_item_not_found


@dataclass(frozen=True)
class SizePriceView:
    size: Size
    price_amd: int


@dataclass(frozen=True)
class MenuItemView:
    id: int
    name: str
    category: Category
    sizes: list[SizePriceView]
    is_available: bool
    image_url: str | None


def to_view(item: MenuItem) -> MenuItemView:
    sizes = [
        SizePriceView(size=size, price_amd=price_for(item, size) or 0)
        for size in offered_sizes(item)
    ]
    return MenuItemView(
        id=item.id,
        name=item.name,
        category=item.category,
        sizes=sizes,
        is_available=item.is_available,
        image_url=item.image_url,
    )


def list_menu(session: Session) -> list[MenuItemView]:
    """All items: coffee, tea, cake; by name inside a category."""
    items = sorted(
        menu_items_repo.list_all(session),
        key=lambda item: (CATEGORY_ORDER[item.category], item.name.casefold(), item.id),
    )
    return [to_view(item) for item in items]


def set_availability(session: Session, menu_item_id: int, is_available: bool) -> MenuItemView:
    """Stop-list switch (the only menu field the barista may change)."""
    with unit_of_work(session):
        item = menu_items_repo.get(session, menu_item_id)
        if item is None:
            raise menu_item_not_found(menu_item_id)
        item.is_available = is_available
    return to_view(item)
