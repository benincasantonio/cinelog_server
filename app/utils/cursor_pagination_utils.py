"""Reusable signed cursor encoding for timestamp-and-UUID and provider-page pagination."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from app.config.cursor_pagination_config import (
    CURSOR_PAGINATION_HMAC_SECRET,
    CURSOR_PAGINATION_VERSION,
)
from app.types import TimestampUUIDCursor
from app.utils.signed_payload_utils import decode_signed_payload, encode_signed_payload

MOVIE_SEARCH_CURSOR_SCOPE = "movie-search"


def encode_timestamp_uuid_cursor(cursor: TimestampUUIDCursor, *, scope: str) -> str:
    """Encode and sign one versioned, scope-bound pagination cursor."""

    if not scope:
        raise ValueError("Cursor scope must not be empty")
    if cursor.timestamp.tzinfo is None or cursor.timestamp.utcoffset() is None:
        raise ValueError("Cursor timestamp must be timezone-aware")

    timestamp = cursor.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
    payload: dict[str, Any] = {
        "v": CURSOR_PAGINATION_VERSION,
        "scope": scope,
        "timestamp": timestamp,
        "id": str(cursor.id),
    }
    return encode_signed_payload(payload, secret=CURSOR_PAGINATION_HMAC_SECRET)


def decode_timestamp_uuid_cursor(value: str, *, expected_scope: str) -> TimestampUUIDCursor:
    """Verify, decode, and strictly validate a scope-bound pagination cursor."""

    try:
        if not expected_scope:
            raise ValueError
        payload = decode_signed_payload(value, secret=CURSOR_PAGINATION_HMAC_SECRET)
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
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid cursor") from exc


def _movie_search_query_digest(query: str) -> str:
    return sha256(query.strip().lower().encode("utf-8")).hexdigest()


def encode_movie_search_cursor(page: int, *, query: str, locale: str) -> str:
    """Sign the next provider page of a search, bound to its normalized query and locale."""

    if page < 1:
        raise ValueError("Cursor page must be positive")
    payload: dict[str, Any] = {
        "v": CURSOR_PAGINATION_VERSION,
        "scope": MOVIE_SEARCH_CURSOR_SCOPE,
        "page": page,
        "q": _movie_search_query_digest(query),
        "locale": locale,
    }
    return encode_signed_payload(payload, secret=CURSOR_PAGINATION_HMAC_SECRET)


def decode_movie_search_cursor(value: str, *, query: str, locale: str) -> int:
    """Return the provider page of a search cursor issued for exactly this query and locale."""

    try:
        payload = decode_signed_payload(value, secret=CURSOR_PAGINATION_HMAC_SECRET)
        if set(payload) != {"v", "scope", "page", "q", "locale"}:
            raise ValueError
        if type(payload["v"]) is not int or payload["v"] != CURSOR_PAGINATION_VERSION:
            raise ValueError
        if payload["scope"] != MOVIE_SEARCH_CURSOR_SCOPE:
            raise ValueError
        page = payload["page"]
        if type(page) is not int or page < 1:
            raise ValueError
        if payload["q"] != _movie_search_query_digest(query) or payload["locale"] != locale:
            raise ValueError
        return page
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid cursor") from exc
