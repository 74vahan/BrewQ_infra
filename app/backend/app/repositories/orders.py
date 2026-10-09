from datetime import date, datetime

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.domain.order_status import ACTIVE_STATUSES, OrderStatus
from app.models.customer import Customer
from app.models.order import Order

# The expression is intentionally identical to the functional unique index
# uq_orders_day_code, so the optimizer answers MAX(code) from that index
# (verified with EXPLAIN in tests/integration/test_order_code_index.py).
DAY_EXPRESSION_SQL = "DATE(created_at + INTERVAL 4 HOUR) = :day"
MAX_CODE_FOR_DAY_SQL = f"SELECT MAX(code) FROM orders WHERE {DAY_EXPRESSION_SQL}"


def max_code_for_day(session: Session, day: date) -> str | None:
    """Highest pickup code issued on the given Yerevan day, or None."""
    return session.execute(text(MAX_CODE_FOR_DAY_SQL), {"day": day}).scalar()


def insert(
    session: Session, *, code: str, customer_id: int, total_amd: int, now: datetime
) -> Order:
    """New order in status NEW; flushing it is where uq_orders_day_code can fire (1062)."""
    order = Order(
        code=code,
        customer_id=customer_id,
        status=OrderStatus.NEW,
        total_amd=total_amd,
        created_at=now,
        updated_at=now,
    )
    session.add(order)
    session.flush()
    return order


def get(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)


def get_own(session: Session, customer_id: int, order_id: int) -> Order | None:
    """An order of this customer; someone else's or a missing id gives None."""
    return session.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
    )


def find_active(session: Session, customer_id: int) -> Order | None:
    return session.scalar(
        select(Order)
        .where(Order.customer_id == customer_id, Order.status.in_(ACTIVE_STATUSES))
        .order_by(Order.id)
        .limit(1)
    )


def list_for_customer(
    session: Session, customer_id: int, *, limit: int, before_id: int | None
) -> list[Order]:
    """History page, newest first (keyset by id). Returns up to `limit` orders."""
    statement = select(Order).where(Order.customer_id == customer_id)
    if before_id is not None:
        statement = statement.where(Order.id < before_id)
    return list(session.scalars(statement.order_by(Order.id.desc()).limit(limit)))


def list_active(session: Session) -> list[Order]:
    """The barista queue: every NEW/IN_PROGRESS/READY order, oldest first."""
    return list(
        session.scalars(
            select(Order)
            .where(Order.status.in_(ACTIVE_STATUSES))
            .order_by(Order.created_at, Order.id)
        )
    )


def list_for_day(session: Session, day: date) -> list[Order]:
    """Every order of one Yerevan day in any status, newest first.

    The day expression is the one of uq_orders_day_code, so the index narrows the scan.
    """
    return list(
        session.scalars(
            select(Order)
            .where(text(DAY_EXPRESSION_SQL).bindparams(day=day))
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
    )


def read_status(session: Session, order_id: int) -> OrderStatus | None:
    """Current status via a locking (latest-committed) read, not the transaction snapshot."""
    return session.scalar(select(Order.status).where(Order.id == order_id).with_for_update())


def compare_and_set_status(
    session: Session,
    order_id: int,
    expected: OrderStatus,
    target: OrderStatus,
    now: datetime,
) -> bool:
    """`UPDATE ... WHERE status = :expected`; True when this call made the change."""
    result = session.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == expected)
        .values(status=target, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def customer_names(session: Session, customer_ids: set[int]) -> dict[int, str | None]:
    if not customer_ids:
        return {}
    rows = session.execute(select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids)))
    return dict(rows.all())
