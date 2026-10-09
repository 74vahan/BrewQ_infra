from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_customer, get_db
from app.api.params import PathId
from app.core.clock import Clock
from app.models.customer import Customer
from app.schemas.common import MAX_ID, ErrorEnvelope
from app.schemas.orders import CurrentOrderResponse, OrderOut, OrderPageResponse
from app.services import checkout as checkout_service
from app.services import orders as orders_service

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    responses={400: {"model": ErrorEnvelope}},
)

Db = Annotated[Session, Depends(get_db)]
CurrentCustomer = Annotated[Customer, Depends(get_customer)]
Now = Annotated[Clock, Depends(get_clock)]


@router.post(
    "",
    status_code=201,
    response_model=OrderOut,
    responses={409: {"model": ErrorEnvelope}},
)
def create_order(db: Db, customer: CurrentCustomer, clock: Now) -> OrderOut:
    """Checkout. No body: the order is made from the server-side cart."""
    return OrderOut.model_validate(checkout_service.checkout(db, customer.id, clock))


@router.get("/current", response_model=CurrentOrderResponse)
def get_current_order(db: Db, customer: CurrentCustomer) -> CurrentOrderResponse:
    order = orders_service.current_order(db, customer.id)
    return CurrentOrderResponse(order=None if order is None else OrderOut.model_validate(order))


@router.get("", response_model=OrderPageResponse)
def list_orders(
    db: Db,
    customer: CurrentCustomer,
    limit: Annotated[int, Query(ge=1, le=orders_service.MAX_PAGE_SIZE)] = (
        orders_service.DEFAULT_PAGE_SIZE
    ),
    before_id: Annotated[int | None, Query(ge=1, le=MAX_ID)] = None,
) -> OrderPageResponse:
    page = orders_service.list_orders(db, customer.id, limit=limit, before_id=before_id)
    return OrderPageResponse(
        items=[OrderOut.model_validate(order) for order in page.items],
        next_before_id=page.next_before_id,
    )


@router.get("/{order_id}", response_model=OrderOut, responses={404: {"model": ErrorEnvelope}})
def get_order(order_id: PathId, db: Db, customer: CurrentCustomer) -> OrderOut:
    return OrderOut.model_validate(orders_service.get_order(db, customer.id, order_id))


@router.post(
    "/{order_id}/cancel",
    response_model=OrderOut,
    responses={404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
def cancel_order(order_id: PathId, db: Db, customer: CurrentCustomer, clock: Now) -> OrderOut:
    order = orders_service.cancel_order(db, customer.id, order_id, clock.now())
    return OrderOut.model_validate(order)
