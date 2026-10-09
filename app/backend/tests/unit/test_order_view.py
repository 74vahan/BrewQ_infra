from datetime import UTC, datetime

import pytest

from app.domain.order_status import OrderStatus
from app.services.order_views import OrderView


def _view(status: OrderStatus) -> OrderView:
    now = datetime(2026, 10, 9, tzinfo=UTC)
    return OrderView(
        id=1,
        code="A-001",
        status=status,
        total_amd=1,
        created_at=now,
        updated_at=now,
        customer_name=None,
    )


@pytest.mark.parametrize("status", list(OrderStatus))
def test_only_new_orders_can_be_cancelled_by_the_client(status):
    assert _view(status).can_cancel is (status is OrderStatus.NEW)


def test_allowed_transitions_follow_the_barista_table():
    assert _view(OrderStatus.NEW).allowed_transitions == [
        OrderStatus.IN_PROGRESS,
        OrderStatus.CANCELLED,
    ]
    assert _view(OrderStatus.IN_PROGRESS).allowed_transitions == [
        OrderStatus.READY,
        OrderStatus.CANCELLED,
    ]
    assert _view(OrderStatus.READY).allowed_transitions == [OrderStatus.PICKED_UP]
    assert _view(OrderStatus.PICKED_UP).allowed_transitions == []
    assert _view(OrderStatus.CANCELLED).allowed_transitions == []
