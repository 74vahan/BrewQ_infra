import pytest

from app.domain.order_code import (
    MAX_DAILY_ORDERS,
    DailyOrderLimitReached,
    format_code,
    next_code,
    parse_code,
)


def test_first_code_of_the_day():
    assert next_code(None) == "A-001"


@pytest.mark.parametrize(
    ("last", "expected"),
    [("A-001", "A-002"), ("A-009", "A-010"), ("A-099", "A-100"), ("A-998", "A-999")],
)
def test_next_code(last, expected):
    assert next_code(last) == expected


def test_limit_reached_after_a999():
    with pytest.raises(DailyOrderLimitReached):
        next_code("A-999")


def test_format_bounds():
    assert format_code(1) == "A-001"
    assert format_code(MAX_DAILY_ORDERS) == "A-999"
    for bad in (0, 1000, -1):
        with pytest.raises(ValueError):
            format_code(bad)


@pytest.mark.parametrize("bad", ["", "A-000", "A-1", "A-0001", "B-001", "a-001", "A-0x1", "A-001 "])
def test_parse_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_code(bad)


def test_string_max_equals_numeric_max():
    codes = [format_code(n) for n in range(1, MAX_DAILY_ORDERS + 1)]
    assert max(codes) == "A-999"
    assert parse_code(max(codes[:500])) == 500
