"""Provider contract for injectable movie search and complete-detail operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.schemas.movie_provider_schemas import (
        MovieDetailsQuery,
        MovieMetadataDTO,
        MovieSearchQuery,
        MovieSearchResultDTO,
    )


class MovieProviderProtocol(Protocol):
    async def search_movie(self, request: MovieSearchQuery) -> MovieSearchResultDTO: ...

    async def get_movie_details(self, request: MovieDetailsQuery) -> MovieMetadataDTO: ...
