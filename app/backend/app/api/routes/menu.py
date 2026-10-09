from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_customer, get_db
from app.models.customer import Customer
from app.schemas.common import ErrorEnvelope
from app.schemas.menu import MenuItemOut, MenuResponse
from app.services import menu as menu_service

router = APIRouter(tags=["menu"])


@router.get(
    "/menu",
    response_model=MenuResponse,
    responses={400: {"model": ErrorEnvelope}},
)
def get_menu(
    db: Annotated[Session, Depends(get_db)],
    _customer: Annotated[Customer, Depends(get_customer)],
) -> MenuResponse:
    """Every item, stop-list included (is_available=false); coffee, tea, cake."""
    items = menu_service.list_menu(db)
    return MenuResponse(items=[MenuItemOut.model_validate(item) for item in items])
