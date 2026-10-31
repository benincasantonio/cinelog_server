"""Stateless HMAC-signed JSON payloads shared by opaque API tokens (cursors, movie references)."""

import hmac
import json
from base64 import b64decode, urlsafe_b64encode
from hashlib import sha256
from typing import Any, cast

_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def _encode_base64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_base64url(value: str) -> bytes:
    if not value or any(character not in _BASE64URL_ALPHABET for character in value):
        raise ValueError
    padding = "=" * (-len(value) % 4)
    return b64decode(value + padding, altchars=b"-_", validate=True)


def _signature(payload_segment: str, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), payload_segment.encode("ascii"), sha256).digest()


def encode_signed_payload(payload: dict[str, Any], *, secret: str) -> str:
    """Serialize a JSON object canonically and sign it as ``<payload>.<signature>``."""

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_segment = _encode_base64url(payload_bytes)
    return f"{payload_segment}.{_encode_base64url(_signature(payload_segment, secret))}"


def decode_signed_payload(value: str, *, secret: str) -> dict[str, object]:
    """Verify a signed token and return its JSON object; raise ``ValueError`` on any defect."""

    try:
        parts = value.split(".")
        if len(parts) != 2:
            raise ValueError

        payload_segment, signature_segment = parts
        payload_bytes = _decode_base64url(payload_segment)
        supplied_signature = _decode_base64url(signature_segment)
        if not hmac.compare_digest(supplied_signature, _signature(payload_segment, secret)):
            raise ValueError

        decoded: object = json.loads(payload_bytes)
        if not isinstance(decoded, dict):
            raise ValueError
        return cast(dict[str, object], decoded)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid signed payload") from exc
