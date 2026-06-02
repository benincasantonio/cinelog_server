"""PostgreSQL movie repository implementation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.models.movie_model import PostgresMovie
from app.repository.repository_base import RepositoryBase
from app.schemas.movie_schemas import MovieCreateRequest, MovieStats, MovieUpdateRequest
from app.schemas.tmdb_schemas import TMDBMovieDetails
from app.utils.datetime_utils import parse_iso_date


class PostgresMovieRepository(RepositoryBase):
    """Repository class for PostgreSQL movie-related operations."""

    async def create_movie(self, request: MovieCreateRequest) -> PostgresMovie:
        """Create a new movie in PostgreSQL."""

        async with self._session_provider() as session:
            movie = PostgresMovie(
                tmdb_id=request.tmdb_id,
                title=request.title,
            )
            session.add(movie)
            await session.commit()
            await session.refresh(movie)
            return movie

    async def update_movie(self, movie_id: UUID, request: MovieUpdateRequest) -> None:
        """Update a movie in PostgreSQL. No-op for missing or soft-deleted rows."""

        async with self._session_provider() as session:
            statement = (
                update(PostgresMovie)
                .where(
                    PostgresMovie.id == movie_id,
                    PostgresMovie.active(),
                )
                .values(
                    title=request.title,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.execute(statement)
            await session.commit()

    async def find_movie_by_id(self, movie_id: UUID) -> PostgresMovie | None:
        """Find an active movie by UUID."""

        async with self._session_provider() as session:
            statement = select(PostgresMovie).where(
                PostgresMovie.id == movie_id,
                PostgresMovie.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_movie_by_tmdb_id(self, tmdb_id: int) -> PostgresMovie | None:
        """Find an active movie by TMDB ID."""

        async with self._session_provider() as session:
            statement = select(PostgresMovie).where(
                PostgresMovie.tmdb_id == tmdb_id,
                PostgresMovie.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def create_from_tmdb_data(self, tmdb_data: TMDBMovieDetails) -> PostgresMovie:
        """Create a movie from TMDB details or return existing row on duplicate TMDB ID."""

        async with self._session_provider() as session:
            movie = PostgresMovie(
                tmdb_id=tmdb_data.id,
                title=tmdb_data.title,
                release_date=parse_iso_date(tmdb_data.release_date),
                overview=tmdb_data.overview,
                poster_path=tmdb_data.poster_path,
                vote_average=tmdb_data.vote_average,
                runtime=tmdb_data.runtime,
                original_language=tmdb_data.original_language,
                tmdb_payload=tmdb_data.model_dump(mode="json"),
                tmdb_last_synced_at=datetime.now(UTC),
            )

            session.add(movie)

            try:
                await session.commit()
                await session.refresh(movie)
                return movie
            except IntegrityError:
                await session.rollback()
                statement = select(PostgresMovie).where(
                    PostgresMovie.tmdb_id == tmdb_data.id,
                    PostgresMovie.active(),
                )
                result = await session.execute(statement)
                existing_movie = result.scalar_one_or_none()
                if existing_movie is None:
                    raise
                return existing_movie

    async def find_movies_by_ids(self, movie_ids: Iterable[UUID]) -> list[PostgresMovie]:
        """Find active movies by UUID set."""

        if not movie_ids:
            return []

        async with self._session_provider() as session:
            statement = select(PostgresMovie).where(
                PostgresMovie.id.in_(movie_ids),
                PostgresMovie.active(),
            )
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def get_movie_stats(self, movie_ids: Iterable[UUID]) -> MovieStats:
        """Compute runtime stats for active movies in PostgreSQL."""

        if not movie_ids:
            return MovieStats(total_runtime=0)

        async with self._session_provider() as session:
            statement = select(func.coalesce(func.sum(PostgresMovie.runtime), 0)).where(
                PostgresMovie.id.in_(movie_ids),
                PostgresMovie.active(),
            )
            result = await session.execute(statement)
            total_runtime = result.scalar_one()
            return MovieStats(total_runtime=int(total_runtime or 0))
