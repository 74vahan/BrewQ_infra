import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import AppError, ErrorCode
from app.schemas.common import ErrorEnvelope
from app.schemas.health import HealthResponse, ReadyResponse

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: the process is up. Does not touch the database."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ErrorEnvelope}},
)
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    """Readiness: the database answers SELECT 1."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        log.warning("Readiness check failed: %s", exc.__class__.__name__)
        raise AppError(ErrorCode.SERVICE_UNAVAILABLE, 503, "Database is unavailable") from exc
    return ReadyResponse(status="ready")
