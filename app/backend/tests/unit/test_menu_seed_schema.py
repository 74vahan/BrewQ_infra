import pytest
from pydantic import ValidationError

from app.schemas.menu_seed import MenuSeed


def item(**overrides):
    base = {"name": "Latte", "category": "coffee", "price_m": 1300}
    return {**base, **overrides}


def test_minimal_item_is_valid():
    seed = MenuSeed.model_validate({"items": [item()]})
    assert seed.items[0].price_s is None
    assert seed.items[0].image_url is None


@pytest.mark.parametrize(
    "bad",
    [
        item(category="soup"),
        item(price_m=0),
        item(price_s=-5),
        item(name="  "),
        item(extra_field=1),
        item(image_url="https://example.com/x.png"),
        item(image_url="/media/menu/../secret"),
    ],
)
def test_invalid_items_are_rejected(bad):
    with pytest.raises(ValidationError):
        MenuSeed.model_validate({"items": [bad]})


def test_duplicate_names_are_rejected_case_insensitively():
    with pytest.raises(ValidationError):
        MenuSeed.model_validate({"items": [item(name="Latte"), item(name="latte")]})
