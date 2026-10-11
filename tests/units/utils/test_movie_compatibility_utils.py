"""The numeric API adapter must select TMDB explicitly, without guessing identity."""

from uuid import uuid4

import pytest

from app.models.movie_model import Movie
from app.models.movie_provider_mapping_model import MovieProviderMapping
from app.utils.movie_compatibility_utils import get_legacy_tmdb_id


def test_legacy_identity_selects_tmdb_among_distinct_providers():
    movie = Movie(
        id=uuid4(),
        title="Film",
        providers=[
            MovieProviderMapping(provider="future", external_id=str(uuid4())),
            MovieProviderMapping(provider="tmdb", external_id="550"),
        ],
    )
    assert get_legacy_tmdb_id(movie) == 550


def test_missing_mapping_is_not_fabricated():
    with pytest.raises(ValueError, match="no TMDB mapping"):
        get_legacy_tmdb_id(Movie(id=uuid4(), title="Film", providers=[]))
