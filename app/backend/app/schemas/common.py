from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorEnvelope(BaseModel):
    """Documentation model of the error envelope (see memory/03-api.md)."""

    error: ErrorBody


def _format_utc(value: datetime) -> str:
    # Always six fractional digits and a literal Z: "2026-10-09T08:15:30.123456Z".
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


UtcTimestamp = Annotated[datetime, PlainSerializer(_format_utc, return_type=str)]

# Ids in URLs and bodies: positive and within BIGINT range (no DB errors on huge numbers).
MAX_ID = 2**63 - 1
IdInt = Annotated[int, Field(strict=True, ge=1, le=MAX_ID)]
# Quantity of a cart line, 1..20 (memory/02-database.md); strict: no "3", no true.
QtyInt = Annotated[int, Field(strict=True, ge=1, le=20)]


class RequestModel(BaseModel):
    """Base of request bodies: unknown fields are a 400 (memory/03-api.md)."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    """Base of responses built from service dataclasses."""

    model_config = ConfigDict(from_attributes=True)
