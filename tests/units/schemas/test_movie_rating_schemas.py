"""Tests for UUID-only movie rating write requests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.movie_rating_schemas import MovieRatingCreateUpdateRequest

MOVIE_ID = uuid4()


def test_rating_request_requires_movie_id():
    request = MovieRatingCreateUpdateRequest.model_validate({"movieId": str(MOVIE_ID), "rating": 8})

    assert request.movie_id == MOVIE_ID
    with pytest.raises(ValidationError):
        MovieRatingCreateUpdateRequest.model_validate({"rating": 8})


@pytest.mark.parametrize(
    "payload",
    [{"tmdbId": 550, "rating": 8}, {"movieId": str(MOVIE_ID), "tmdbId": 550, "rating": 8}],
)
def test_rating_request_rejects_tmdb_id(payload):
    with pytest.raises(ValidationError) as exc_info:
        MovieRatingCreateUpdateRequest.model_validate(payload)

    assert any(error["type"] == "extra_forbidden" for error in exc_info.value.errors())
