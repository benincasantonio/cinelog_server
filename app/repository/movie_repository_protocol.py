from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol, TypeVar

from app.schemas.movie_import_schemas import MovieCreateDTO
from app.schemas.movie_provider_schemas import MovieSourceReferenceDTO
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

    async def find_movie_by_provider(
        self, source: MovieSourceReferenceDTO, *, include_deleted: bool = False
    ) -> MovieType | None:
        """Resolve an opaque source identity; deleted identities can be inspected before import."""

    async def find_movies_by_ids(self, movie_ids: Iterable[IdType]) -> Sequence[MovieType]:
        """Find multiple movies by a set of unique identifiers."""

    async def find_movies_by_external_ids(self, provider: str, external_ids: Iterable[str]) -> Mapping[str, MovieType]:
        """Map each already-imported external ID of one provider to its movie, including deleted movies."""
