import pytest

from app.domain.device_id import normalize_device_id

VALID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_valid_uuid_v4_is_kept():
    assert normalize_device_id(VALID) == VALID


def test_uppercase_is_normalized_to_lower_case():
    assert normalize_device_id(VALID.upper()) == VALID
    assert normalize_device_id("3F2504E0-4F89-41D3-9A0C-0305E82C3301") == (
        "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
    )


@pytest.mark.parametrize("variant", "89abAB")
def test_rfc4122_variants_are_accepted(variant):
    assert normalize_device_id(f"aaaaaaaa-aaaa-4aaa-{variant}aaa-aaaaaaaaaaaa") is not None


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not-a-uuid",
        "aaaaaaaa-aaaa-1aaa-8aaa-aaaaaaaaaaaa",  # version 1
        "aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa",  # version 5
        "aaaaaaaa-aaaa-4aaa-caaa-aaaaaaaaaaaa",  # wrong variant
        "aaaaaaaa-aaaa-4aaa-0aaa-aaaaaaaaaaaa",  # wrong variant
        "aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa",  # no hyphens
        "{aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa}",  # braces
        "urn:uuid:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        " aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaag",
        "gggggggg-gggg-4ggg-8ggg-gggggggggggg",
    ],
)
def test_everything_else_is_rejected(raw):
    assert normalize_device_id(raw) is None
