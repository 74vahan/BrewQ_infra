"""Static checks of seed/menu.json and the media files it references."""

from pathlib import Path

from app.core.config import DEFAULT_MEDIA_DIR
from app.services.menu_seed import DEFAULT_SEED_FILE, load_seed


def test_seed_file_is_valid_and_matches_the_plan():
    seed = load_seed(DEFAULT_SEED_FILE)
    by_category: dict[str, list] = {}
    for item in seed.items:
        by_category.setdefault(item.category.value, []).append(item)

    coffee, tea, cake = by_category["coffee"], by_category["tea"], by_category["cake"]
    assert 4 <= len(coffee) <= 6
    assert all(i.price_s and i.price_l for i in coffee)
    assert 2 <= len(tea) <= 3
    assert 2 <= len(cake) <= 3
    assert all(i.price_s is None and i.price_l is None for i in cake)


def test_every_image_url_has_a_file():
    for item in load_seed(DEFAULT_SEED_FILE).items:
        assert item.image_url is not None
        relative = Path(item.image_url.removeprefix("/media/"))
        assert (DEFAULT_MEDIA_DIR / relative).is_file(), item.image_url
