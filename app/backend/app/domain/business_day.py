"""Yerevan business day.

Asia/Yerevan is a constant UTC+4 (no DST since 2012). The same expression
`DATE(created_at + INTERVAL 4 HOUR)` is used by the functional unique index
`uq_orders_day_code`, so the shift lives here and in that index only.
A unit test compares this constant with tzdata and fails if it ever changes.
"""

from datetime import UTC, date, datetime, time, timedelta

YEREVAN_OFFSET = timedelta(hours=4)


def business_day(now_utc: datetime) -> date:
    """Yerevan calendar date for a timezone-aware instant."""
    if now_utc.tzinfo is None:
        raise ValueError("business_day requires a timezone-aware datetime")
    return (now_utc.astimezone(UTC) + YEREVAN_OFFSET).date()


def business_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """[start, end) of the Yerevan day as aware UTC datetimes."""
    start = datetime.combine(day, time.min, tzinfo=UTC) - YEREVAN_OFFSET
    return start, start + timedelta(days=1)
