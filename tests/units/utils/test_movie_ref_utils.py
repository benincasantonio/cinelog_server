"""Tests for signed, stateless search-result movie references."""

import pytest

from app.schemas.movie_provider_schemas import MovieSourceReferenceDTO
from app.utils.movie_ref_utils import decode_movie_ref, encode_movie_ref
from app.utils.signed_payload_utils import decode_signed_payload, encode_signed_payload

TEST_MOVIE_REF_HMAC_SECRET = "test-movie-ref-hmac-secret"
TMDB_550 = MovieSourceReferenceDTO(source="tmdb", external_id="550")


def _signed(payload: dict[str, object], secret: str = TEST_MOVIE_REF_HMAC_SECRET) -> str:
    return encode_signed_payload(payload, secret=secret)


def test_movie_ref_round_trips_provider_identity():
    movie_ref = encode_movie_ref(TMDB_550)

    assert decode_movie_ref(movie_ref) == TMDB_550
    assert decode_signed_payload(movie_ref, secret=TEST_MOVIE_REF_HMAC_SECRET) == {
        "v": 1,
        "provider": "tmdb",
        "externalId": "550",
    }


def test_movie_ref_is_stable_for_the_same_identity():
    assert encode_movie_ref(TMDB_550) == encode_movie_ref(TMDB_550.model_copy())


@pytest.mark.parametrize(
    "movie_ref",
    [
        "",
        "tmdb:550",
        "550",
        _signed({"v": 1, "provider": "tmdb", "externalId": "550"}, secret="another-secret"),
        _signed({"v": 2, "provider": "tmdb", "externalId": "550"}),
        _signed({"v": True, "provider": "tmdb", "externalId": "550"}),
        _signed({"v": 1, "provider": "imdb", "externalId": "tt0137523"}),
        _signed({"v": 1, "provider": "tmdb", "externalId": ""}),
        _signed({"v": 1, "provider": "tmdb", "externalId": 550}),
        _signed({"v": 1, "provider": "tmdb"}),
        _signed({"v": 1, "provider": "tmdb", "externalId": "550", "exp": 0}),
    ],
)
def test_movie_ref_rejects_invalid_references(movie_ref):
    with pytest.raises(ValueError, match="Invalid movie reference"):
        decode_movie_ref(movie_ref)
