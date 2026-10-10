from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar

from app.schemas.movie_import_schemas import MovieCreateDTO
from app.schemas.movie_schemas import MovieUpdateRequest

IdType = TypeVar("IdType", contravariant=True)
MovieType = TypeVar("MovieType", covariant=True)


class MovieIdentityUnavailableError(Exception):
    """Raised when a source identity belongs to a soft-deleted movie and cannot be imported again."""


class MovieRepositoryProtocol(Protocol[IdType, MovieType]):
    """Protocol for movie repository implementations."""

    async def create_movie(self, data: MovieCreateDTO) -> MovieType:
        """Persist a Cinelog import or return the existing active movie for its source identity.

        Raises ``MovieIdentityUnavailableError`` when the identity belongs to a soft-deleted movie.
        """

    async def update_movie(self, movie_id: IdType, request: MovieUpdateRequest) -> None:
        """Update an existing movie in the database."""

    async def find_movie_by_id(self, movie_id: IdType) -> MovieType | None:
        """Find a movie by its unique identifier."""

    async def find_movie_by_tmdb_id(self, tmdb_id: int) -> MovieType | None:
        """Find a movie by its TMDB ID."""

    async def find_movies_by_ids(self, movie_ids: Iterable[IdType]) -> Sequence[MovieType]:
        """Find multiple movies by a set of unique identifiers."""
