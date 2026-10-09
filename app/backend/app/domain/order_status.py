"""Order status machine: a pure table of allowed transitions."""

from enum import StrEnum


class OrderStatus(StrEnum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    PICKED_UP = "PICKED_UP"
    CANCELLED = "CANCELLED"


class Actor(StrEnum):
    CLIENT = "client"
    BARISTA = "barista"


ACTIVE_STATUSES: frozenset[OrderStatus] = frozenset(
    {OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.READY}
)

# Ordered tuples: the forward step first, then cancellation. The barista panel
# draws its buttons from this order.
_TRANSITIONS: dict[Actor, dict[OrderStatus, tuple[OrderStatus, ...]]] = {
    Actor.BARISTA: {
        OrderStatus.NEW: (OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED),
        OrderStatus.IN_PROGRESS: (OrderStatus.READY, OrderStatus.CANCELLED),
        OrderStatus.READY: (OrderStatus.PICKED_UP,),
    },
    Actor.CLIENT: {
        OrderStatus.NEW: (OrderStatus.CANCELLED,),
    },
}


def allowed_targets(current: OrderStatus, actor: Actor) -> tuple[OrderStatus, ...]:
    return _TRANSITIONS[actor].get(current, ())


def can_transition(current: OrderStatus, target: OrderStatus, actor: Actor) -> bool:
    return target in allowed_targets(current, actor)


def is_active(status: OrderStatus) -> bool:
    return status in ACTIVE_STATUSES
