"""PostgreSQL movie-rating repository implementation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models.movie_rating_model import MovieRating
from app.repository.repository_base import RepositoryBase
from app.schemas.movie_rating_schemas import MovieRatingStats


class MovieRatingRepository(RepositoryBase):
    """Repository class for PostgreSQL movie-rating operations."""

    async def find_movie_rating_by_user_and_movie(
        self,
        user_id: UUID,
        movie_id: UUID,
    ) -> MovieRating | None:
        """Find an active movie rating by user ID and movie ID."""

        async with self._session_provider() as session:
            statement = select(MovieRating).where(
                MovieRating.user_id == user_id,
                MovieRating.movie_id == movie_id,
                MovieRating.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_movie_rating_by_user_and_tmdb(
        self,
        user_id: UUID,
        tmdb_id: int,
    ) -> MovieRating | None:
        """Find an active movie rating by user ID and TMDB ID."""

        async with self._session_provider() as session:
            statement = select(MovieRating).where(
                MovieRating.user_id == user_id,
                MovieRating.tmdb_id == tmdb_id,
                MovieRating.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def create_update_movie_rating(
        self,
        user_id: UUID,
        movie_id: UUID,
        rating: int,
        comment: str | None,
        tmdb_id: int,
    ) -> MovieRating:
        """Insert or update a movie rating using PostgreSQL native upsert."""

        async with self._session_provider() as session:
            statement = (
                insert(MovieRating)
                .values(
                    user_id=user_id,
                    movie_id=movie_id,
                    tmdb_id=tmdb_id,
                    rating=rating,
                    review=comment,
                )
                .on_conflict_do_update(
                    index_elements=[MovieRating.user_id, MovieRating.tmdb_id],
                    set_={
                        "movie_id": movie_id,
                        "rating": rating,
                        "review": comment,
                        "updated_at": func.now(),
                        "deleted": False,
                        "deleted_at": None,
                    },
                )
                .returning(MovieRating.id)
            )
            result = await session.execute(statement)
            rating_id = result.scalar_one()
            await session.commit()

            rating_record = await session.get(MovieRating, rating_id)
            if rating_record is None:
                raise LookupError("Movie rating not found after upsert.")

            return rating_record

    async def find_movie_ratings_by_user_and_movie_ids(
        self,
        user_id: UUID,
        movie_ids: Iterable[UUID],
    ) -> Sequence[MovieRating]:
        """Find active movie ratings for a user across movie IDs."""

        movie_ids = list(movie_ids)
        if not movie_ids:
            return []

        async with self._session_provider() as session:
            statement = select(MovieRating).where(
                MovieRating.user_id == user_id,
                MovieRating.movie_id.in_(movie_ids),
                MovieRating.active(),
            )
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def get_user_movie_ratings_average(
        self,
        user_id: UUID,
        movie_ids: Iterable[UUID],
    ) -> MovieRatingStats:
        """Compute average movie rating and count for the user's active ratings."""

        movie_ids = list(movie_ids)
        if not movie_ids:
            return MovieRatingStats(average_rating=0.0, total_ratings=0)

        async with self._session_provider() as session:
            statement = select(
                func.avg(MovieRating.rating),
                func.count(MovieRating.id),
            ).where(
                MovieRating.user_id == user_id,
                MovieRating.movie_id.in_(movie_ids),
                MovieRating.active(),
                MovieRating.rating.is_not(None),
            )
            result = await session.execute(statement)
            average_rating, total_ratings = result.one()
            return MovieRatingStats(
                average_rating=float(average_rating or 0.0),
                total_ratings=int(total_ratings or 0),
            )
