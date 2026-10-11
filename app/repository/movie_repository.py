"""PostgreSQL movie repository implementation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.models.movie_model import Movie
from app.models.movie_provider_mapping_model import MovieProviderMapping
from app.repository.movie_repository_protocol import MovieIdentityUnavailableError
from app.repository.repository_base import RepositoryBase
from app.schemas.movie_import_schemas import MovieCreateDTO
from app.schemas.movie_provider_schemas import MovieSourceReferenceDTO
from app.schemas.movie_schemas import MovieUpdateRequest
from app.types import MovieProviderName


def _movie_by_provider_query(source: MovieSourceReferenceDTO) -> Select[tuple[Movie]]:
    """Select a source identity, including deleted films, with loaded mappings."""
    return (
        select(Movie)
        .join(MovieProviderMapping, MovieProviderMapping.movie_id == Movie.id)
        .options(selectinload(Movie.providers))
        .where(
            MovieProviderMapping.provider == source.source,
            MovieProviderMapping.external_id == source.external_id,
        )
    )


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
            statement = (
                select(Movie)
                .options(selectinload(Movie.providers))
                .where(
                    Movie.id == movie_id,
                    Movie.active(),
                )
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_movie_by_provider(
        self, source: MovieSourceReferenceDTO, *, include_deleted: bool = False
    ) -> Movie | None:
        """Resolve an opaque source identity, optionally including reserved deleted films."""
        async with self._session_provider() as session:
            statement = _movie_by_provider_query(source)
            if not include_deleted:
                statement = statement.where(Movie.active())
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def create_movie(self, data: MovieCreateDTO) -> Movie:
        """Atomically import a movie and mapping, or return the existing source identity.

        A losing concurrent import rolls back its entire transaction, including the
        candidate movie. Only the external-identity conflict is handled; unrelated
        constraints and persistence failures propagate without committing anything.
        """
        if data.source.source not in MovieProviderName:
            raise ValueError(f"Movie source {data.source.source!r} is not currently enabled")

        async with self._session_provider() as session:
            movie = Movie(
                title=data.title,
                release_date=datetime.combine(data.release_date, time.min) if data.release_date else None,
                overview=data.overview,
                poster_path=data.poster_path,
                vote_average=data.vote_average,
                runtime=data.runtime,
                original_language=data.original_language,
            )
            session.add(movie)
            await session.flush()
            result = await session.execute(
                insert(MovieProviderMapping)
                .values(
                    movie_id=movie.id,
                    provider=data.source.source,
                    external_id=data.source.external_id,
                    payload=data.source_payload,
                    last_synced_at=data.observed_at,
                )
                .on_conflict_do_nothing(constraint="pk_movie_providers")
                .returning(MovieProviderMapping.movie_id)
            )
            if result.scalar_one_or_none() is None:
                await session.rollback()
                statement = _movie_by_provider_query(data.source)
                existing = (await session.execute(statement)).scalar_one()
                if existing.deleted:
                    raise MovieIdentityUnavailableError(f"{data.source.source}:{data.source.external_id}")
                return existing

            await session.commit()
            await session.refresh(movie, attribute_names=["providers"])
            return movie

    async def find_movies_by_ids(self, movie_ids: Iterable[UUID]) -> list[Movie]:
        """Find active movies by UUID set."""

        movie_ids = list(movie_ids)
        if not movie_ids:
            return []

        async with self._session_provider() as session:
            statement = (
                select(Movie)
                .options(selectinload(Movie.providers))
                .where(
                    Movie.id.in_(movie_ids),
                    Movie.active(),
                )
            )
            result = await session.execute(statement)
            return list(result.scalars().all())
