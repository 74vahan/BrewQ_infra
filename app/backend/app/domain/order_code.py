"""Pickup code `A-001`..`A-999`, unique per Yerevan day."""

import re

CODE_PREFIX = "A-"
MAX_DAILY_ORDERS = 999

_CODE_RE = re.compile(r"^A-(\d{3})$")


class DailyOrderLimitReached(Exception):
    """The last code of the day (A-999) is already issued."""


def format_code(number: int) -> str:
    if not 1 <= number <= MAX_DAILY_ORDERS:
        raise ValueError(f"order number out of range: {number}")
    return f"{CODE_PREFIX}{number:03d}"


def parse_code(code: str) -> int:
    match = _CODE_RE.match(code)
    if match is None or int(match.group(1)) == 0:
        raise ValueError(f"malformed order code: {code!r}")
    return int(match.group(1))


def next_code(last_code: str | None) -> str:
    """Code following the day's current maximum (None = no orders yet today).

    Codes are zero-padded, so the string MAX equals the numeric maximum.
    """
    number = 1 if last_code is None else parse_code(last_code) + 1
    if number > MAX_DAILY_ORDERS:
        raise DailyOrderLimitReached
    return format_code(number)
