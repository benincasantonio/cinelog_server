"""Temporary numeric identity adapter for the released movie/log/rating APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.types import MovieProviderName

if TYPE_CHECKING:
    from app.models.movie_model import Movie


def get_legacy_tmdb_id(movie: Movie) -> int:
    """Read the numeric API identity from already-loaded mappings, without I/O."""
    for mapping in movie.providers:
        if mapping.provider == MovieProviderName.TMDB:
            return int(mapping.external_id)
    raise ValueError(f"Movie {movie.id} has no TMDB mapping required by the legacy API")
