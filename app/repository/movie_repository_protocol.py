from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar

from app.schemas.movie_schemas import MovieCreateRequest, MovieUpdateRequest
from app.schemas.tmdb_schemas import TMDBMovieDetails

IdType = TypeVar("IdType", contravariant=True)
MovieType = TypeVar("MovieType", covariant=True)


class MovieRepositoryProtocol(Protocol[IdType, MovieType]):
    """Protocol for movie repository implementations."""

    async def create_movie(self, request: MovieCreateRequest) -> MovieType:
        """Create a new movie in the database."""

    async def update_movie(self, movie_id: IdType, request: MovieUpdateRequest) -> None:
        """Update an existing movie in the database."""

    async def find_movie_by_id(self, movie_id: IdType) -> MovieType | None:
        """Find a movie by its unique identifier."""

    async def find_movie_by_tmdb_id(self, tmdb_id: int) -> MovieType | None:
        """Find a movie by its TMDB ID."""

    async def create_from_tmdb_data(self, tmdb_data: TMDBMovieDetails) -> MovieType:
        """Create a movie from TMDB details or return existing row on duplicate TMDB ID."""

    async def find_movies_by_ids(self, movie_ids: Iterable[IdType]) -> Sequence[MovieType]:
        """Find multiple movies by a set of unique identifiers."""
