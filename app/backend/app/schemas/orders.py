from pydantic import BaseModel

from app.domain.order_status import OrderStatus
from app.domain.sizes import Size
from app.schemas.common import ResponseModel, UtcTimestamp


class OrderLineOut(ResponseModel):
    menu_item_id: int
    name: str
    size: Size
    qty: int
    unit_price_amd: int
    line_total_amd: int


class OrderOut(ResponseModel):
    id: int
    code: str
    status: OrderStatus
    total_amd: int
    created_at: UtcTimestamp
    updated_at: UtcTimestamp
    can_cancel: bool
    items: list[OrderLineOut]


class CurrentOrderResponse(BaseModel):
    order: OrderOut | None


class OrderPageResponse(BaseModel):
    items: list[OrderOut]
    next_before_id: int | None
