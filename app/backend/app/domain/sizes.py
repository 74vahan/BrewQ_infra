"""Sizes and the "a size is offered only if its price exists" rule."""

from enum import StrEnum
from typing import Protocol


class Size(StrEnum):
    S = "S"
    M = "M"
    L = "L"


class PricedItem(Protocol):
    price_s: int | None
    price_m: int
    price_l: int | None


def price_for(item: PricedItem, size: Size) -> int | None:
    """Price of the item in the given size, or None if that size is not offered."""
    if size is Size.S:
        return item.price_s
    if size is Size.M:
        return item.price_m
    return item.price_l


def offered_sizes(item: PricedItem) -> list[Size]:
    """Offered sizes in the fixed order S, M, L."""
    return [size for size in Size if price_for(item, size) is not None]
