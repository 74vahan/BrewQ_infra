"""Error envelope: {"error": {"code", "message", "details"}} (see memory/03-api.md)."""

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DEVICE_ID_MISSING = "DEVICE_ID_MISSING"
    DEVICE_ID_INVALID = "DEVICE_ID_INVALID"
    SIZE_NOT_OFFERED = "SIZE_NOT_OFFERED"
    BARISTA_INVALID_PASSWORD = "BARISTA_INVALID_PASSWORD"
    BARISTA_UNAUTHORIZED = "BARISTA_UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    MENU_ITEM_NOT_FOUND = "MENU_ITEM_NOT_FOUND"
    CART_ITEM_NOT_FOUND = "CART_ITEM_NOT_FOUND"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    MENU_ITEM_UNAVAILABLE = "MENU_ITEM_UNAVAILABLE"
    CART_QTY_LIMIT_EXCEEDED = "CART_QTY_LIMIT_EXCEEDED"
    CART_EMPTY = "CART_EMPTY"
    CART_HAS_UNAVAILABLE_ITEMS = "CART_HAS_UNAVAILABLE_ITEMS"
    ACTIVE_ORDER_EXISTS = "ACTIVE_ORDER_EXISTS"
    DAILY_ORDER_LIMIT_REACHED = "DAILY_ORDER_LIMIT_REACHED"
    ORDER_NOT_CANCELLABLE = "ORDER_NOT_CANCELLABLE"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    # Fallback for framework HTTP errors the contract has no dedicated code for.
    HTTP_ERROR = "HTTP_ERROR"


class AppError(Exception):
    """Domain/service error that becomes an error envelope in exactly one place."""

    def __init__(
        self,
        code: ErrorCode,
        http_status: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message
        self.details = details or {}


def error_response(
    http_status: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code.value, "message": message, "details": details or {}}},
    )


def _field_path(loc: tuple[Any, ...]) -> str:
    # loc looks like ("body", "items", 0, "qty"); the first element is the source.
    return ".".join(str(part) for part in loc[1:]) or str(loc[0] if loc else "")


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.http_status, exc.code, exc.message, exc.details)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [{"field": _field_path(tuple(e["loc"])), "issue": e["type"]} for e in exc.errors()]
    return error_response(
        400, ErrorCode.VALIDATION_ERROR, "Request validation failed", {"fields": fields}
    )


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return error_response(404, ErrorCode.NOT_FOUND, "Resource not found")
    if exc.status_code == 405:
        return error_response(405, ErrorCode.METHOD_NOT_ALLOWED, "Method not allowed")
    if exc.status_code >= 500:
        return error_response(exc.status_code, ErrorCode.INTERNAL_ERROR, "Internal server error")
    return error_response(exc.status_code, ErrorCode.HTTP_ERROR, "Request failed")


async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    log.error("Unhandled exception", exc_info=exc)
    return error_response(500, ErrorCode.INTERNAL_ERROR, "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
