from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.business_day import YEREVAN_OFFSET, business_day, business_day_bounds_utc

YEREVAN = ZoneInfo("Asia/Yerevan")


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_midnight_boundary():
    assert business_day(utc(2026, 10, 9, 19, 59, 59, 999999)) == date(2026, 10, 9)
    assert business_day(utc(2026, 10, 9, 20, 0, 0)) == date(2026, 10, 10)


def test_yerevan_23_59_and_00_01_are_different_days():
    assert business_day(utc(2026, 10, 9, 19, 59)) == date(2026, 10, 9)
    assert business_day(utc(2026, 10, 9, 20, 1)) == date(2026, 10, 10)


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        business_day(datetime(2026, 10, 9, 12, 0))


def test_non_utc_aware_input_is_converted():
    yerevan_local = datetime(2026, 10, 10, 0, 30, tzinfo=YEREVAN)
    assert business_day(yerevan_local) == date(2026, 10, 10)


def test_constant_matches_tzdata_for_years_ahead():
    """Fails if tzdata ever gives Yerevan a DST/offset change.

    Then the constant and the functional index must be changed together (migration).
    """
    instant = utc(2026, 1, 1)
    end = utc(2040, 1, 1)
    while instant < end:
        assert instant.astimezone(YEREVAN).utcoffset() == YEREVAN_OFFSET, instant
        assert business_day(instant) == instant.astimezone(YEREVAN).date(), instant
        instant += timedelta(hours=7, minutes=13)


def test_bounds_cover_exactly_one_yerevan_day():
    start, end = business_day_bounds_utc(date(2026, 10, 10))
    assert start == utc(2026, 10, 9, 20, 0)
    assert end == utc(2026, 10, 10, 20, 0)
    assert business_day(start) == date(2026, 10, 10)
    assert business_day(end - timedelta(microseconds=1)) == date(2026, 10, 10)
    assert business_day(end) == date(2026, 10, 11)
