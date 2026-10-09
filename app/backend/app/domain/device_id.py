"""X-Device-Id: a UUID v4 in the canonical hyphenated form (memory/03-api.md)."""

import re

# version nibble 4, variant nibble 8/9/a/b (RFC 4122); case-insensitive
_UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def normalize_device_id(raw: str) -> str | None:
    """Lower-cased UUID v4, or None if `raw` is not a canonical UUID v4."""
    if _UUID_V4_RE.fullmatch(raw) is None:
        return None
    return raw.lower()
