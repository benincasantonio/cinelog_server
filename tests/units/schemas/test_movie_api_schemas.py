"""Tests for the public UUID-only movie API contract."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.movie_api_schemas import MovieResolveRequest, MovieSearchResultItem

ITEM_FIELDS = {
    "title": "Fight Club",
    "overview": "",
    "release_date": "",
    "vote_average": 8.4,
    "genre_ids": [],
    "original_language": "en",
    "original_title": "Fight Club",
}


@pytest.mark.parametrize("identity", [{"id": uuid4()}, {"movie_ref": "opaque-ref"}])
def test_search_item_carries_exactly_one_identity(identity):
    item = MovieSearchResultItem(**ITEM_FIELDS, **identity)

    serialized = item.model_dump(by_alias=True)
    assert [serialized["id"], serialized["movieRef"]].count(None) == 1
    assert "tmdbId" not in serialized


@pytest.mark.parametrize("identity", [{}, {"id": uuid4(), "movie_ref": "opaque-ref"}])
def test_search_item_rejects_missing_or_double_identity(identity):
    with pytest.raises(ValidationError, match="Exactly one of id and movieRef must be set"):
        MovieSearchResultItem(**ITEM_FIELDS, **identity)


def test_resolve_request_accepts_only_movie_ref():
    assert MovieResolveRequest.model_validate({"movieRef": "opaque-ref"}).movie_ref == "opaque-ref"

    with pytest.raises(ValidationError):
        MovieResolveRequest.model_validate({"movieRef": "opaque-ref", "tmdbId": 550})
    with pytest.raises(ValidationError):
        MovieResolveRequest.model_validate({"movieRef": ""})
