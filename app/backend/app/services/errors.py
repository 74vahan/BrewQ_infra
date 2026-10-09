"""Factories for the AppErrors that several services raise (codes: memory/03-api.md)."""

from app.core.errors import AppError, ErrorCode
from app.domain.order_status import OrderStatus


def menu_item_not_found(menu_item_id: int) -> AppError:
    return AppError(
        ErrorCode.MENU_ITEM_NOT_FOUND, 404, "Menu item not found", {"menu_item_id": menu_item_id}
    )


def cart_item_not_found(cart_item_id: int) -> AppError:
    return AppError(
        ErrorCode.CART_ITEM_NOT_FOUND, 404, "Cart item not found", {"cart_item_id": cart_item_id}
    )


def order_not_found(order_id: int) -> AppError:
    return AppError(ErrorCode.ORDER_NOT_FOUND, 404, "Order not found", {"order_id": order_id})


def order_not_cancellable(status: OrderStatus) -> AppError:
    return AppError(
        ErrorCode.ORDER_NOT_CANCELLABLE,
        409,
        "Order can be cancelled only while it is NEW",
        {"status": status.value},
    )
