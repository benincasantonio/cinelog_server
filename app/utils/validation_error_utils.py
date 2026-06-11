"""Sanitization of request validation errors before they are returned to clients."""

from collections.abc import Sequence
from typing import Any, cast

from fastapi.encoders import jsonable_encoder

# Echoing the submitted value back would leak credentials (passwords, reset
# codes) into browser devtools, proxy/WAF logs, and monitoring tools, so the
# whole field is dropped instead of redacting a denylist of keys.
_STRIPPED_KEYS = {"input", "url"}


def sanitize_validation_errors(errors: Sequence[Any]) -> list[Any]:
    """Return validation error entries without the submitted request values.

    Keeps ``type``, ``loc``, ``msg``, and ``ctx`` so clients retain full
    field-level feedback.
    """

    sanitized = [
        {key: _encode_value(value) for key, value in error.items() if key not in _STRIPPED_KEYS} for error in errors
    ]
    return cast(list[Any], jsonable_encoder(sanitized))


def _encode_value(value: Any) -> Any:
    # Custom validators surface as ``ctx: {"error": ValueError(...)}``, which
    # jsonable_encoder would flatten to an empty dict instead of the message.
    if isinstance(value, dict):
        return {key: _encode_value(inner) for key, inner in value.items()}
    if isinstance(value, Exception):
        return str(value)
    return value
