import pytest

from app.domain.customer_name import MAX_NAME_LENGTH, normalize_name

# Armenian "Ani" and Russian "Ivan", built from code points to keep sources ASCII.
ARMENIAN = "".join(chr(c) for c in (0x531, 0x576, 0x56B))
RUSSIAN = "".join(chr(c) for c in (0x418, 0x432, 0x430, 0x43D))


def test_name_is_trimmed():
    assert normalize_name("  Ani  ") == "Ani"


@pytest.mark.parametrize("blank", [None, "", "   ", "\t\n "])
def test_blank_becomes_none(blank):
    assert normalize_name(blank) is None


def test_unicode_names_are_kept():
    assert normalize_name(ARMENIAN) == ARMENIAN
    assert normalize_name(RUSSIAN) == RUSSIAN
    assert normalize_name("A" + chr(0x1F600)) == "A" + chr(0x1F600)


def test_length_limit_counts_characters_not_bytes():
    assert normalize_name(ARMENIAN[0] * MAX_NAME_LENGTH) is not None
    with pytest.raises(ValueError):
        normalize_name(ARMENIAN[0] * (MAX_NAME_LENGTH + 1))


@pytest.mark.parametrize(
    "bad", ["A\x00B", "A\nB", "A\tB", "A\x7fB", "A" + chr(0x2028) + "B", "A\ud800B"]
)
def test_control_characters_are_rejected(bad):
    with pytest.raises(ValueError):
        normalize_name(bad)
