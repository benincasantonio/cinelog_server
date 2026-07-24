"""Reusable signed cursor encoding for timestamp-and-UUID pagination."""

import hmac
import json
from base64 import b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from typing import TypedDict, cast
from uuid import UUID

from app.config.cursor_pagination_config import (
    CURSOR_PAGINATION_HMAC_SECRET,
    CURSOR_PAGINATION_VERSION,
)
from app.types import TimestampUUIDCursor

_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


class _TimestampUUIDCursorPayload(TypedDict):
    """Closed serialized cursor payload signed by this module."""

    v: int
    scope: str
    timestamp: str
    id: str


def _encode_base64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_base64url(value: str) -> bytes:
    if not value or any(character not in _BASE64URL_ALPHABET for character in value):
        raise ValueError
    padding = "=" * (-len(value) % 4)
    return b64decode(value + padding, altchars=b"-_", validate=True)


def _signature(payload_segment: str) -> bytes:
    return hmac.new(
        CURSOR_PAGINATION_HMAC_SECRET.encode("utf-8"),
        payload_segment.encode("ascii"),
        sha256,
    ).digest()


def encode_timestamp_uuid_cursor(cursor: TimestampUUIDCursor, *, scope: str) -> str:
    """Encode and sign one versioned, scope-bound pagination cursor."""

    if not scope:
        raise ValueError("Cursor scope must not be empty")
    if cursor.timestamp.tzinfo is None or cursor.timestamp.utcoffset() is None:
        raise ValueError("Cursor timestamp must be timezone-aware")

    timestamp = cursor.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
    payload: _TimestampUUIDCursorPayload = {
        "v": CURSOR_PAGINATION_VERSION,
        "scope": scope,
        "timestamp": timestamp,
        "id": str(cursor.id),
    }
    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_segment = _encode_base64url(payload_bytes)
    signature_segment = _encode_base64url(_signature(payload_segment))
    return f"{payload_segment}.{signature_segment}"


def decode_timestamp_uuid_cursor(value: str, *, expected_scope: str) -> TimestampUUIDCursor:
    """Verify, decode, and strictly validate a scope-bound pagination cursor."""

    try:
        if not expected_scope:
            raise ValueError
        parts = value.split(".")
        if len(parts) != 2:
            raise ValueError

        payload_segment, signature_segment = parts
        payload_bytes = _decode_base64url(payload_segment)
        supplied_signature = _decode_base64url(signature_segment)
        if not hmac.compare_digest(supplied_signature, _signature(payload_segment)):
            raise ValueError

        decoded: object = json.loads(payload_bytes)
        if not isinstance(decoded, dict):
            raise ValueError
        payload = cast(dict[str, object], decoded)
        if set(payload) != {"v", "scope", "timestamp", "id"}:
            raise ValueError
        if type(payload["v"]) is not int or payload["v"] != CURSOR_PAGINATION_VERSION:
            raise ValueError
        if payload["scope"] != expected_scope:
            raise ValueError

        timestamp_value = payload["timestamp"]
        id_value = payload["id"]
        if not isinstance(timestamp_value, str) or not isinstance(id_value, str):
            raise ValueError

        normalized_timestamp = f"{timestamp_value[:-1]}+00:00" if timestamp_value.endswith("Z") else timestamp_value
        timestamp = datetime.fromisoformat(normalized_timestamp)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError

        return TimestampUUIDCursor(
            timestamp=timestamp.astimezone(UTC),
            id=UUID(id_value),
        )
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc
