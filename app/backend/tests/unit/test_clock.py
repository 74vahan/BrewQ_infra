from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.clock import FakeClock, SystemClock


def test_system_clock_is_aware_utc():
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fake_clock_moves():
    clock = FakeClock(datetime(2026, 10, 9, 19, 59, 59, tzinfo=UTC))
    clock.advance(seconds=2)
    assert clock.now() == datetime(2026, 10, 9, 20, 0, 1, tzinfo=UTC)
    clock.set(datetime(2026, 1, 1, 3, 0, tzinfo=timezone(timedelta(hours=4))))
    assert clock.now() == datetime(2025, 12, 31, 23, 0, tzinfo=UTC)


def test_fake_clock_rejects_naive():
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 1, 1))
