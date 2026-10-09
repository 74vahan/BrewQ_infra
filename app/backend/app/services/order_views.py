"""Order read models shared by the client and the barista APIs."""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.order_status import Actor, OrderStatus, allowed_targets, can_transition
from app.domain.sizes import Size
from app.models.order import Order
from app.repositories import order_items as order_items_repo
from app.repositories import orders as orders_repo


@dataclass(frozen=True)
class OrderLineView:
    menu_item_id: int
    name: str
    size: Size
    qty: int
    unit_price_amd: int
    line_total_amd: int


@dataclass(frozen=True)
class OrderView:
    id: int
    code: str
    status: OrderStatus
    total_amd: int
    created_at: datetime
    updated_at: datetime
    customer_name: str | None
    items: list[OrderLineView] = field(default_factory=list)

    @property
    def can_cancel(self) -> bool:
        """The client may cancel only while the order is NEW."""
        return can_transition(self.status, OrderStatus.CANCELLED, Actor.CLIENT)

    @property
    def allowed_transitions(self) -> list[OrderStatus]:
        """Buttons the barista panel may draw, in display order."""
        return list(allowed_targets(self.status, Actor.BARISTA))


def build_order_views(session: Session, orders: list[Order]) -> list[OrderView]:
    """Views in the order given; two extra queries regardless of how many orders."""
    lines_by_order: dict[int, list[OrderLineView]] = {order.id: [] for order in orders}
    for line, item in order_items_repo.list_for_orders(session, set(lines_by_order)):
        lines_by_order[line.order_id].append(
            OrderLineView(
                menu_item_id=item.id,
                name=item.name,
                size=line.size,
                qty=line.qty,
                unit_price_amd=line.unit_price_amd,
                line_total_amd=line.unit_price_amd * line.qty,
            )
        )
    names = orders_repo.customer_names(session, {order.customer_id for order in orders})
    return [
        OrderView(
            id=order.id,
            code=order.code,
            status=order.status,
            total_amd=order.total_amd,
            created_at=order.created_at,
            updated_at=order.updated_at,
            customer_name=names.get(order.customer_id),
            items=lines_by_order[order.id],
        )
        for order in orders
    ]


def build_order_view(session: Session, order: Order) -> OrderView:
    return build_order_views(session, [order])[0]
