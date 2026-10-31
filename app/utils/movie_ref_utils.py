"""Signed movieRef tokens naming a provider identity that a search result has not yet materialized.

A movieRef is an API abstraction, not a secret: the HMAC only proves the backend issued it.
It carries no expiry and needs no storage; resolution re-validates it and looks up the mapping.
"""

from typing import Any

from app.config.movie_ref_config import MOVIE_REF_HMAC_SECRET, MOVIE_REF_VERSION
from app.schemas.movie_provider_schemas import MovieSourceReferenceDTO
from app.types import MovieProviderName
from app.utils.signed_payload_utils import decode_signed_payload, encode_signed_payload


def encode_movie_ref(source: MovieSourceReferenceDTO) -> str:
    """Sign a provider identity as an opaque movieRef."""

    payload: dict[str, Any] = {
        "v": MOVIE_REF_VERSION,
        "provider": source.source,
        "externalId": source.external_id,
    }
    return encode_signed_payload(payload, secret=MOVIE_REF_HMAC_SECRET)


def decode_movie_ref(value: str) -> MovieSourceReferenceDTO:
    """Verify a movieRef and return its enabled provider identity; raise ``ValueError`` otherwise."""

    try:
        payload = decode_signed_payload(value, secret=MOVIE_REF_HMAC_SECRET)
        if set(payload) != {"v", "provider", "externalId"}:
            raise ValueError
        if type(payload["v"]) is not int or payload["v"] != MOVIE_REF_VERSION:
            raise ValueError
        provider, external_id = payload["provider"], payload["externalId"]
        if not isinstance(provider, str) or provider not in MovieProviderName:
            raise ValueError
        if not isinstance(external_id, str) or not external_id:
            raise ValueError
        return MovieSourceReferenceDTO(source=provider, external_id=external_id)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid movie reference") from exc
