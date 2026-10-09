from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_customer, get_db
from app.api.params import PathId
from app.core.clock import Clock
from app.models.customer import Customer
from app.schemas.cart import AddCartItemRequest, CartOut, SetCartItemQtyRequest
from app.schemas.common import ErrorEnvelope
from app.services import cart as cart_service

router = APIRouter(
    prefix="/cart",
    tags=["cart"],
    responses={400: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)

Db = Annotated[Session, Depends(get_db)]
CurrentCustomer = Annotated[Customer, Depends(get_customer)]
Now = Annotated[Clock, Depends(get_clock)]


@router.get("", response_model=CartOut)
def get_cart(db: Db, customer: CurrentCustomer) -> CartOut:
    return CartOut.model_validate(cart_service.get_cart(db, customer.id))


@router.post("/items", response_model=CartOut, responses={409: {"model": ErrorEnvelope}})
def add_cart_item(
    body: AddCartItemRequest, db: Db, customer: CurrentCustomer, clock: Now
) -> CartOut:
    cart = cart_service.add_item(
        db, customer.id, body.menu_item_id, body.size, body.qty, clock.now()
    )
    return CartOut.model_validate(cart)


@router.patch("/items/{cart_item_id}", response_model=CartOut)
def set_cart_item_qty(
    cart_item_id: PathId,
    body: SetCartItemQtyRequest,
    db: Db,
    customer: CurrentCustomer,
    clock: Now,
) -> CartOut:
    cart = cart_service.set_qty(db, customer.id, cart_item_id, body.qty, clock.now())
    return CartOut.model_validate(cart)


@router.delete("/items/{cart_item_id}", response_model=CartOut)
def remove_cart_item(cart_item_id: PathId, db: Db, customer: CurrentCustomer) -> CartOut:
    return CartOut.model_validate(cart_service.remove_item(db, customer.id, cart_item_id))


@router.delete("", response_model=CartOut)
def clear_cart(db: Db, customer: CurrentCustomer) -> CartOut:
    return CartOut.model_validate(cart_service.clear_cart(db, customer.id))
