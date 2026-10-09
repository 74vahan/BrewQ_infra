"""Menu as code: upsert seed/menu.json into menu_items.

Rules (memory/02-database.md): upsert by name, updates category/price_*/image_url,
NEVER touches is_available (that field belongs to the barista), deletes nothing.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.repositories import menu_items as menu_items_repo
from app.schemas.menu_seed import MenuSeed, MenuSeedItem

log = logging.getLogger(__name__)

# app/backend/app/services/menu_seed.py -> parents[2] is the backend root
DEFAULT_SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "menu.json"

_SYNCED_FIELDS = ("category", "price_s", "price_m", "price_l", "image_url")


@dataclass(frozen=True)
class SeedResult:
    created: int
    updated: int
    unchanged: int
    orphaned: tuple[str, ...]


def load_seed(path: Path = DEFAULT_SEED_FILE) -> MenuSeed:
    return MenuSeed.model_validate(json.loads(path.read_text(encoding="utf-8")))


def apply_seed(session: Session, seed: MenuSeed) -> SeedResult:
    created = updated = unchanged = 0
    for entry in seed.items:
        existing = menu_items_repo.get_by_name(session, entry.name)
        if existing is None:
            session.add(_new_item(entry))
            created += 1
        elif _sync(existing, entry):
            updated += 1
        else:
            unchanged += 1
    session.flush()

    wanted = {entry.name.casefold() for entry in seed.items}
    orphaned = tuple(
        item.name
        for item in menu_items_repo.list_all(session)
        if item.name.casefold() not in wanted
    )
    for name in orphaned:
        log.warning(
            "Menu item %r is in the database but not in the seed file; left untouched", name
        )
    session.commit()
    return SeedResult(created, updated, unchanged, orphaned)


def _new_item(entry: MenuSeedItem) -> MenuItem:
    # is_available is omitted on purpose: the database default (TRUE) applies.
    return MenuItem(
        name=entry.name,
        category=entry.category,
        price_s=entry.price_s,
        price_m=entry.price_m,
        price_l=entry.price_l,
        image_url=entry.image_url,
    )


def _sync(item: MenuItem, entry: MenuSeedItem) -> bool:
    changed = False
    for field in _SYNCED_FIELDS:
        value = getattr(entry, field)
        if getattr(item, field) != value:
            setattr(item, field, value)
            changed = True
    return changed
