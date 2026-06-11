import pytest

from app.utils.id_utils import is_valid_uuid


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("e340c5bd-a268-5cb5-9e3c-2413648520da", True),
        ("not-a-uuid", False),
        ("507f1f77bcf86cd799439011", False),
    ],
)
def test_is_valid_uuid(value: str, expected: bool):
    assert is_valid_uuid(value) is expected
