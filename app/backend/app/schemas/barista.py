from typing import Literal

from pydantic import BaseModel, Field, StrictBool

from app.domain.order_status import OrderStatus
from app.schemas.common import RequestModel, ResponseModel, UtcTimestamp
from app.schemas.orders import OrderLineOut


class LoginRequest(RequestModel):
    password: str = Field(max_length=1024)


class LoginResponse(BaseModel):
    token: str
    expires_at: UtcTimestamp


class BaristaOrderOut(ResponseModel):
    id: int
    code: str
    status: OrderStatus
    total_amd: int
    created_at: UtcTimestamp
    updated_at: UtcTimestamp
    customer_name: str | None
    allowed_transitions: list[OrderStatus]
    items: list[OrderLineOut]


class BaristaOrdersResponse(BaseModel):
    items: list[BaristaOrderOut]


class ChangeStatusRequest(RequestModel):
    # NEW is not a target: orders only start there.
    to: Literal[
        OrderStatus.IN_PROGRESS,
        OrderStatus.READY,
        OrderStatus.PICKED_UP,
        OrderStatus.CANCELLED,
    ]


class UpdateMenuItemRequest(RequestModel):
    is_available: StrictBool
