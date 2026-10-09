"""Customer display name rules: trimmed, 1..40 characters, no control characters."""

import unicodedata

MAX_NAME_LENGTH = 40

# Control, surrogate, line and paragraph separators. Surrogates cannot be stored as UTF-8.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cs", "Zl", "Zp"})


def normalize_name(raw: str | None) -> str | None:
    """Trimmed name; None for None/blank input. Raises ValueError if the name is invalid."""
    if raw is None:
        return None
    name = raw.strip()
    if not name:
        return None
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"name is longer than {MAX_NAME_LENGTH} characters")
    if any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in name):
        raise ValueError("name contains control characters")
    return name
