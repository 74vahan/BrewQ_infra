"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.models.cart_item import CartItem
from app.models.customer import Customer
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.order_item import OrderItem

__all__ = ["CartItem", "Customer", "MenuItem", "Order", "OrderEvent", "OrderItem"]
