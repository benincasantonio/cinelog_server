"""PostgreSQL movie repository implementation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models.movie_model import Movie
from app.repository.movie_repository_protocol import MovieIdentityUnavailableError
from app.repository.repository_base import RepositoryBase
from app.schemas.movie_import_schemas import MovieCreateDTO
from app.schemas.movie_schemas import MovieUpdateRequest


class MovieRepository(RepositoryBase):
    """Repository class for PostgreSQL movie-related operations."""

    async def update_movie(self, movie_id: UUID, request: MovieUpdateRequest) -> None:
        """Update a movie in PostgreSQL. No-op for missing or soft-deleted rows."""

        async with self._session_provider() as session:
            statement = (
                update(Movie)
                .where(
                    Movie.id == movie_id,
                    Movie.active(),
                )
                .values(
                    title=request.title,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.execute(statement)
            await session.commit()

    async def find_movie_by_id(self, movie_id: UUID) -> Movie | None:
        """Find an active movie by UUID."""

        async with self._session_provider() as session:
            statement = select(Movie).where(
                Movie.id == movie_id,
                Movie.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_movie_by_tmdb_id(self, tmdb_id: int) -> Movie | None:
        """Find an active movie by TMDB ID."""

        async with self._session_provider() as session:
            statement = select(Movie).where(
                Movie.tmdb_id == tmdb_id,
                Movie.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def create_movie(self, data: MovieCreateDTO) -> Movie:
        """Persist a Cinelog import or return the active movie with the same source identity.

        Source data uses the existing TMDB columns until #248.
        """

        if data.source.source != "tmdb":
            raise ValueError("The current storage schema supports only the tmdb source")
        external_id = int(data.source.external_id)

        async with self._session_provider() as session:
            movie = Movie(
                tmdb_id=external_id,
                title=data.title,
                release_date=datetime.combine(data.release_date, time.min) if data.release_date else None,
                overview=data.overview,
                poster_path=data.poster_path,
                vote_average=data.vote_average,
                runtime=data.runtime,
                original_language=data.original_language,
                tmdb_payload=data.source_payload,
                tmdb_last_synced_at=data.observed_at,
            )

            session.add(movie)

            try:
                await session.commit()
                await session.refresh(movie)
                return movie
            except IntegrityError as error:
                await session.rollback()
                statement = select(Movie).where(Movie.tmdb_id == external_id)
                result = await session.execute(statement)
                existing_movie = result.scalar_one_or_none()
                if existing_movie is None:
                    raise
                if existing_movie.deleted:
                    raise MovieIdentityUnavailableError(f"tmdb:{external_id}") from error
                return existing_movie

    async def find_movies_by_ids(self, movie_ids: Iterable[UUID]) -> list[Movie]:
        """Find active movies by UUID set."""

        movie_ids = list(movie_ids)
        if not movie_ids:
            return []

        async with self._session_provider() as session:
            statement = select(Movie).where(
                Movie.id.in_(movie_ids),
                Movie.active(),
            )
            result = await session.execute(statement)
            return list(result.scalars().all())
