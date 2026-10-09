from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_db, require_barista
from app.api.params import PathId
from app.core.clock import Clock
from app.schemas.barista import BaristaOrderOut, BaristaOrdersResponse, ChangeStatusRequest
from app.schemas.common import ErrorEnvelope
from app.services import barista_orders
from app.services.barista_orders import Scope

router = APIRouter(
    prefix="/barista/orders",
    tags=["barista"],
    dependencies=[Depends(require_barista)],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
    },
)

Db = Annotated[Session, Depends(get_db)]
Now = Annotated[Clock, Depends(get_clock)]


@router.get("", response_model=BaristaOrdersResponse)
def list_orders(
    db: Db, clock: Now, scope: Annotated[Scope, Query()] = "active"
) -> BaristaOrdersResponse:
    """`active` = the queue (oldest first); `today` = this Yerevan day, any status."""
    orders = barista_orders.list_orders(db, scope, clock.now())
    return BaristaOrdersResponse(items=[BaristaOrderOut.model_validate(order) for order in orders])


@router.post(
    "/{order_id}/status",
    response_model=BaristaOrderOut,
    responses={404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
def change_status(
    order_id: PathId, body: ChangeStatusRequest, db: Db, clock: Now
) -> BaristaOrderOut:
    order = barista_orders.change_status(db, order_id, body.to, clock.now())
    return BaristaOrderOut.model_validate(order)
