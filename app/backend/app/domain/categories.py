from enum import StrEnum


class Category(StrEnum):
    COFFEE = "coffee"
    TEA = "tea"
    CAKE = "cake"


# Menu order: coffee, tea, cake (memory/03-api.md, GET /api/menu).
CATEGORY_ORDER: dict[Category, int] = {category: rank for rank, category in enumerate(Category)}
