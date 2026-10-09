from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.db.types import UtcDateTime


def test_bind_converts_aware_to_naive_utc():
    value = datetime(2026, 10, 10, 0, 30, 1, 123456, tzinfo=timezone(timedelta(hours=4)))
    bound = UtcDateTime().process_bind_param(value, None)
    assert bound == datetime(2026, 10, 9, 20, 30, 1, 123456)
    assert bound.tzinfo is None


def test_bind_rejects_naive():
    with pytest.raises(ValueError):
        UtcDateTime().process_bind_param(datetime(2026, 1, 1), None)


def test_result_is_aware_utc():
    result = UtcDateTime().process_result_value(datetime(2026, 1, 1, 12), None)
    assert result == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert UtcDateTime().process_result_value(None, None) is None
