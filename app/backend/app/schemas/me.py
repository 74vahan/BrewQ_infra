from typing import Any

from pydantic import field_validator

from app.domain.customer_name import normalize_name
from app.schemas.common import RequestModel, ResponseModel


class MeResponse(ResponseModel):
    name: str | None


class UpdateMeRequest(RequestModel):
    name: str | None

    @field_validator("name", mode="before")
    @classmethod
    def _normalize(cls, value: Any) -> Any:
        # Non-strings fall through so that type validation reports them.
        if value is None or isinstance(value, str):
            return normalize_name(value)
        return value
