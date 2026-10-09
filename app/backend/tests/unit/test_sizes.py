from dataclasses import dataclass

from app.domain.sizes import Size, offered_sizes, price_for


@dataclass
class Item:
    price_m: int
    price_s: int | None = None
    price_l: int | None = None


def test_full_size_range():
    item = Item(price_s=1100, price_m=1300, price_l=1500)
    assert [price_for(item, s) for s in Size] == [1100, 1300, 1500]
    assert offered_sizes(item) == [Size.S, Size.M, Size.L]


def test_single_price_item_offers_only_m():
    item = Item(price_m=1500)
    assert price_for(item, Size.S) is None
    assert price_for(item, Size.M) == 1500
    assert price_for(item, Size.L) is None
    assert offered_sizes(item) == [Size.M]


def test_partial_sizes_keep_s_m_l_order():
    assert offered_sizes(Item(price_m=900, price_l=1200)) == [Size.M, Size.L]
