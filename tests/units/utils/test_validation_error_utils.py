"""Unit tests for validation error sanitization."""

from app.utils.validation_error_utils import sanitize_validation_errors


def test_strips_dict_input_from_body_level_error():
    errors = [
        {
            "type": "missing",
            "loc": ("body", "dateOfBirth"),
            "msg": "Field required",
            "input": {"email": "not-an-email", "password": "SuperSecret1!"},
        }
    ]

    sanitized = sanitize_validation_errors(errors)

    assert sanitized == [{"type": "missing", "loc": ["body", "dateOfBirth"], "msg": "Field required"}]


def test_strips_scalar_input_from_field_level_error():
    errors = [
        {
            "type": "string_too_short",
            "loc": ("body", "password"),
            "msg": "String should have at least 8 characters",
            "input": "short",
            "ctx": {"min_length": 8},
        }
    ]

    sanitized = sanitize_validation_errors(errors)

    assert sanitized[0] == {
        "type": "string_too_short",
        "loc": ["body", "password"],
        "msg": "String should have at least 8 characters",
        "ctx": {"min_length": 8},
    }


def test_strips_pydantic_docs_url():
    errors = [
        {
            "type": "missing",
            "loc": ("body",),
            "msg": "Field required",
            "input": None,
            "url": "https://errors.pydantic.dev/2/v/missing",
        }
    ]

    sanitized = sanitize_validation_errors(errors)

    assert sanitized == [{"type": "missing", "loc": ["body"], "msg": "Field required"}]


def test_entry_without_input_is_unchanged():
    errors = [{"type": "json_invalid", "loc": ("body",), "msg": "JSON decode error"}]

    assert sanitize_validation_errors(errors) == [{"type": "json_invalid", "loc": ["body"], "msg": "JSON decode error"}]


def test_non_serializable_ctx_is_json_encoded():
    errors = [
        {
            "type": "value_error",
            "loc": ("body", "handle"),
            "msg": "Value error, invalid handle",
            "input": "bad handle",
            "ctx": {"error": ValueError("invalid handle")},
        }
    ]

    sanitized = sanitize_validation_errors(errors)

    assert sanitized[0]["ctx"] == {"error": "invalid handle"}
    assert "input" not in sanitized[0]
