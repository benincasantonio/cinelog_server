"""Tests for the shared stateless HMAC-signed payload encoding."""

import pytest

from app.utils.signed_payload_utils import decode_signed_payload, encode_signed_payload


def test_signed_payload_round_trips_as_url_safe_token():
    token = encode_signed_payload({"b": 2, "a": "x"}, secret="secret")

    assert set(token) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.")
    assert token.count(".") == 1
    assert decode_signed_payload(token, secret="secret") == {"a": "x", "b": 2}


def test_signed_payload_is_canonical():
    assert encode_signed_payload({"a": 1, "b": 2}, secret="secret") == encode_signed_payload(
        {"b": 2, "a": 1}, secret="secret"
    )


def test_signed_payload_rejects_another_secret():
    token = encode_signed_payload({"a": 1}, secret="secret")

    with pytest.raises(ValueError, match="Invalid signed payload"):
        decode_signed_payload(token, secret="other-secret")


def test_signed_payload_rejects_modified_payload():
    payload_segment, signature = encode_signed_payload({"a": 1}, secret="secret").split(".")
    forged_segment = encode_signed_payload({"a": 2}, secret="secret").split(".")[0]

    with pytest.raises(ValueError):
        decode_signed_payload(f"{forged_segment}.{signature}", secret="secret")
    assert payload_segment != forged_segment


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "a+b.c", "!!.??", "e30"])
def test_signed_payload_rejects_malformed_tokens(token):
    with pytest.raises(ValueError, match="Invalid signed payload"):
        decode_signed_payload(token, secret="secret")


def test_signed_payload_rejects_signed_non_object_json():
    from app.utils import signed_payload_utils as module

    segment = module._encode_base64url(b"[1,2]")
    token = f"{segment}.{module._encode_base64url(module._signature(segment, 'secret'))}"

    with pytest.raises(ValueError):
        decode_signed_payload(token, secret="secret")
