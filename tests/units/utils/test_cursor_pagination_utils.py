"""Tests for reusable signed timestamp-and-UUID cursors."""

import hmac
import json
from base64 import b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest

from app.types import TimestampUUIDCursor
from app.utils.cursor_pagination_utils import (
    decode_movie_search_cursor,
    decode_timestamp_uuid_cursor,
    encode_movie_search_cursor,
    encode_timestamp_uuid_cursor,
)

TEST_CURSOR_PAGINATION_HMAC_SECRET = "test-cursor-pagination-hmac-secret"
TEST_SCOPE = "notifications.list"


def _encode_base64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_base64url(value: str) -> bytes:
    return b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def _signed_bytes(payload: bytes) -> str:
    payload_segment = _encode_base64url(payload)
    signature = hmac.new(
        TEST_CURSOR_PAGINATION_HMAC_SECRET.encode("utf-8"),
        payload_segment.encode("ascii"),
        sha256,
    ).digest()
    return f"{payload_segment}.{_encode_base64url(signature)}"


def _signed_payload(payload: dict[str, object]) -> str:
    return _signed_bytes(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "v": 1,
        "scope": TEST_SCOPE,
        "timestamp": "2026-07-18T08:30:00Z",
        "id": str(uuid4()),
    }
    return {**payload, **overrides}


def test_timestamp_uuid_cursor_round_trips_as_signed_url_safe_token():
    cursor = TimestampUUIDCursor(
        timestamp=datetime(2026, 7, 18, 8, 30, 15, 123456, tzinfo=UTC),
        id=uuid4(),
    )

    encoded = encode_timestamp_uuid_cursor(cursor, scope=TEST_SCOPE)

    payload_segment, signature_segment = encoded.split(".")
    assert "=" not in encoded
    assert payload_segment.replace("-", "").replace("_", "").isalnum()
    assert signature_segment.replace("-", "").replace("_", "").isalnum()
    assert decode_timestamp_uuid_cursor(encoded, expected_scope=TEST_SCOPE) == cursor


def test_timestamp_uuid_cursor_rejects_modified_signature():
    cursor = TimestampUUIDCursor(timestamp=datetime(2026, 7, 18, 8, 30, tzinfo=UTC), id=uuid4())
    encoded = encode_timestamp_uuid_cursor(cursor, scope=TEST_SCOPE)
    payload_segment, signature_segment = encoded.split(".")
    modified_signature = bytearray(_decode_base64url(signature_segment))
    modified_signature[0] ^= 1

    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_timestamp_uuid_cursor(
            f"{payload_segment}.{_encode_base64url(bytes(modified_signature))}",
            expected_scope=TEST_SCOPE,
        )


def test_timestamp_uuid_cursor_rejects_wrong_scope():
    cursor = TimestampUUIDCursor(timestamp=datetime(2026, 7, 18, 8, 30, tzinfo=UTC), id=uuid4())
    encoded = encode_timestamp_uuid_cursor(cursor, scope="users.list")

    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_timestamp_uuid_cursor(encoded, expected_scope=TEST_SCOPE)


def test_timestamp_uuid_cursor_rejects_wrong_version_with_valid_signature():
    encoded = _signed_payload(_valid_payload(v=2))

    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_timestamp_uuid_cursor(encoded, expected_scope=TEST_SCOPE)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-base64!",
        "one.two.three",
        _signed_bytes(b"not-json"),
        _signed_payload({"v": 1, "scope": TEST_SCOPE}),
        _signed_payload(_valid_payload(timestamp="2026-07-18T08:30:00")),
        _signed_payload(_valid_payload(timestamp="bad-date")),
        _signed_payload(_valid_payload(id="bad-id")),
        _signed_payload(_valid_payload(extra=True)),
    ],
)
def test_timestamp_uuid_cursor_rejects_malformed_payloads(value: str):
    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_timestamp_uuid_cursor(value, expected_scope=TEST_SCOPE)


def test_timestamp_uuid_cursor_encoder_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        encode_timestamp_uuid_cursor(
            TimestampUUIDCursor(timestamp=datetime(2026, 7, 18, 8, 30), id=uuid4()),
            scope=TEST_SCOPE,
        )


def _search_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "v": 1,
        "scope": "movie-search",
        "page": 2,
        "q": sha256(b"fight club").hexdigest(),
        "locale": "en-US",
    }
    return {**payload, **overrides}


def test_movie_search_cursor_round_trips_for_the_normalized_query_and_locale():
    cursor = encode_movie_search_cursor(2, query="  Fight CLUB ", locale="en-US")

    assert decode_movie_search_cursor(cursor, query="fight club", locale="en-US") == 2
    assert cursor == _signed_payload(_search_payload())


@pytest.mark.parametrize(
    ("query", "locale"),
    [("another film", "en-US"), ("fight club", "it-IT")],
)
def test_movie_search_cursor_is_bound_to_query_and_locale(query, locale):
    cursor = encode_movie_search_cursor(2, query="fight club", locale="en-US")

    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_movie_search_cursor(cursor, query=query, locale=locale)


@pytest.mark.parametrize(
    "payload",
    [
        _search_payload(v=2),
        _search_payload(scope="notifications.list"),
        _search_payload(page=0),
        _search_payload(page="2"),
        _search_payload(page=True),
        {**_search_payload(), "extra": 1},
    ],
)
def test_movie_search_cursor_rejects_invalid_signed_payloads(payload):
    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_movie_search_cursor(_signed_payload(payload), query="fight club", locale="en-US")


def test_movie_search_cursor_rejects_timestamp_cursor():
    cursor = _signed_payload(_valid_payload())

    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_movie_search_cursor(cursor, query="fight club", locale="en-US")


def test_movie_search_cursor_requires_positive_page():
    with pytest.raises(ValueError, match="Cursor page must be positive"):
        encode_movie_search_cursor(0, query="film", locale="en-US")
