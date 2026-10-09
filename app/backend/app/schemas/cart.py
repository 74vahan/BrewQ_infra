from typing import Literal

from pydantic import Field

from app.domain.sizes import Size
from app.schemas.common import IdInt, QtyInt, RequestModel, ResponseModel


class AddCartItemRequest(RequestModel):
    menu_item_id: IdInt
    size: Size
    qty: QtyInt = 1


class SetCartItemQtyRequest(RequestModel):
    qty: QtyInt


class CartLineOut(ResponseModel):
    id: int
    menu_item_id: int
    name: str
    image_url: str | None
    size: Size
    qty: int
    unit_price_amd: int | None = Field(description="null only when problem is size_not_offered")
    line_total_amd: int | None = Field(description="null only when problem is size_not_offered")
    is_available: bool
    problem: Literal["unavailable", "size_not_offered"] | None


class CartOut(ResponseModel):
    items: list[CartLineOut]
    total_amd: int
    can_checkout: bool
