from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_customer, get_db
from app.models.customer import Customer
from app.schemas.common import ErrorEnvelope
from app.schemas.me import MeResponse, UpdateMeRequest
from app.services import customer as customer_service

router = APIRouter(tags=["me"], responses={400: {"model": ErrorEnvelope}})


@router.get("/me", response_model=MeResponse)
def get_me(customer: Annotated[Customer, Depends(get_customer)]) -> MeResponse:
    return MeResponse(name=customer.name)


@router.put("/me", response_model=MeResponse)
def update_me(
    body: UpdateMeRequest,
    db: Annotated[Session, Depends(get_db)],
    customer: Annotated[Customer, Depends(get_customer)],
) -> MeResponse:
    name = customer_service.set_name(db, customer.id, body.name)
    return MeResponse(name=name)
