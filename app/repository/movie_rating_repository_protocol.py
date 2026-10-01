from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar

IdType = TypeVar("IdType", contravariant=True)

MovieRatingType = TypeVar("MovieRatingType", covariant=True)


class MovieRatingRepositoryProtocol(Protocol[IdType, MovieRatingType]):
    async def find_movie_rating_by_user_and_movie(self, user_id: IdType, movie_id: IdType) -> MovieRatingType | None:
        """Find a movie rating by user ID and movie ID."""

    async def find_movie_rating_by_user_and_tmdb(self, user_id: IdType, tmdb_id: int) -> MovieRatingType | None:
        """Find a movie rating by user ID and TMDB ID."""

    async def create_update_movie_rating(
        self,
        user_id: IdType,
        movie_id: IdType,
        rating: int,
        comment: str | None,
        tmdb_id: int,
    ) -> MovieRatingType:
        """Create or update a movie rating for a specific user and movie."""

    async def find_movie_ratings_by_user_and_movie_ids(
        self, user_id: IdType, movie_ids: Iterable[IdType]
    ) -> Sequence[MovieRatingType]:
        """Find all movie ratings for a list of movie IDs."""
