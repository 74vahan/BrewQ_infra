from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_barista
from app.api.params import PathId
from app.schemas.barista import UpdateMenuItemRequest
from app.schemas.common import ErrorEnvelope
from app.schemas.menu import MenuItemOut, MenuResponse
from app.services import menu as menu_service

router = APIRouter(
    prefix="/barista/menu",
    tags=["barista"],
    dependencies=[Depends(require_barista)],
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)

Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=MenuResponse)
def get_menu(db: Db) -> MenuResponse:
    items = menu_service.list_menu(db)
    return MenuResponse(items=[MenuItemOut.model_validate(item) for item in items])


@router.patch(
    "/{menu_item_id}",
    response_model=MenuItemOut,
    responses={404: {"model": ErrorEnvelope}},
)
def update_menu_item(menu_item_id: PathId, body: UpdateMenuItemRequest, db: Db) -> MenuItemOut:
    """Stop-list switch; is_available is the only field that can change."""
    item = menu_service.set_availability(db, menu_item_id, body.is_available)
    return MenuItemOut.model_validate(item)
