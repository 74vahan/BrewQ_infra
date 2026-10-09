from pydantic import BaseModel

from app.domain.categories import Category
from app.domain.sizes import Size
from app.schemas.common import ResponseModel


class SizePrice(ResponseModel):
    size: Size
    price_amd: int


class MenuItemOut(ResponseModel):
    id: int
    name: str
    category: Category
    sizes: list[SizePrice]
    is_available: bool
    image_url: str | None


class MenuResponse(BaseModel):
    items: list[MenuItemOut]
