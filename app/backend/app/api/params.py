"""Shared request parameter types."""

from typing import Annotated

from fastapi import Path

from app.schemas.common import MAX_ID

# Positive id in a URL path; anything else is a 400 VALIDATION_ERROR.
PathId = Annotated[int, Path(ge=1, le=MAX_ID)]
