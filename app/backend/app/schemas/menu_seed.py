"""Shape of seed/menu.json ("menu as code")."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.categories import Category

_Price = Annotated[int, Field(gt=0, le=4_000_000_000)]
_ImageUrl = Annotated[str, StringConstraints(max_length=255, pattern=r"^/media/menu/[\w.-]+$")]


class MenuSeedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    category: Category
    price_s: _Price | None = None
    price_m: _Price
    price_l: _Price | None = None
    image_url: _ImageUrl | None = None


class MenuSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MenuSeedItem]

    @model_validator(mode="after")
    def _names_are_unique(self) -> "MenuSeed":
        # MySQL compares names case-insensitively (utf8mb4_0900_ai_ci).
        names = [item.name.casefold() for item in self.items]
        if len(names) != len(set(names)):
            raise ValueError("duplicate item names in menu seed")
        return self
