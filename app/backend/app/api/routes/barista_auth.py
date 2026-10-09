from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_clock
from app.core.clock import Clock
from app.core.config import Settings
from app.schemas.barista import LoginRequest, LoginResponse
from app.schemas.common import ErrorEnvelope
from app.services import barista_auth

router = APIRouter(tags=["barista"])


@router.post(
    "/barista/login",
    response_model=LoginResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
def login(
    body: LoginRequest,
    settings: Annotated[Settings, Depends(get_app_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> LoginResponse:
    token, expires_at = barista_auth.login(settings, body.password, clock.now())
    return LoginResponse(token=token, expires_at=expires_at)
