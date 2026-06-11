"""Unit tests for ``MovieRatingRepository``."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.movie_model import Movie
from app.models.movie_rating_model import MovieRating
from app.models.user_model import User
from app.repository.movie_rating_repository import MovieRatingRepository


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    """Create a fresh database per test and return an async SQLAlchemy engine."""
    dbname = f"cinelog_movie_rating_test_{uuid4().hex[:8]}"

    with DatabaseJanitor(
        user=postgresql_proc.user,
        host=postgresql_proc.host,
        port=postgresql_proc.port,
        dbname=dbname,
        version=postgresql_proc.version,
        password=postgresql_proc.password,
    ):
        engine = create_async_engine(_async_url(postgresql_proc, dbname))
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await connection.run_sync(Base.metadata.create_all)

        try:
            yield engine
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(pg_engine):
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def repository(session_factory) -> MovieRatingRepository:
    @asynccontextmanager
    async def _provider():
        async with session_factory() as session:
            yield session

    return MovieRatingRepository(session_provider=_provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _add(seed_session: AsyncSession, *entities) -> None:
    seed_session.add_all(entities)
    await seed_session.commit()
    for entity in entities:
        await seed_session.refresh(entity)


async def _seed_fk_entities(seed_session: AsyncSession) -> tuple[User, Movie, Movie]:
    user = User(
        email="ratings@example.com",
        handle="ratings-user",
        first_name="Ratings",
        last_name="User",
        date_of_birth=date(1990, 1, 1),
    )
    movie_a = Movie(tmdb_id=550, title="Fight Club")
    movie_b = Movie(tmdb_id=551, title="Movie B")
    await _add(seed_session, user, movie_a, movie_b)
    return user, movie_a, movie_b


@pytest.mark.asyncio
async def test_create_update_movie_rating_creates_new_row(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)

    rating = await repository.create_update_movie_rating(
        user_id=user.id,
        movie_id=movie.id,
        rating=8,
        comment="Great movie!",
        tmdb_id=movie.tmdb_id,
    )

    assert rating.id is not None
    assert rating.user_id == user.id
    assert rating.movie_id == movie.id
    assert rating.rating == 8
    assert rating.review == "Great movie!"
    assert rating.deleted is False


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_movie_excludes_deleted_and_unknown(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    active = MovieRating(user_id=user.id, movie_id=movie.id, tmdb_id=movie.tmdb_id, rating=9, review="Loved it")
    deleted = MovieRating(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=999,
        rating=7,
        review="Deleted",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)

    found = await repository.find_movie_rating_by_user_and_movie(user.id, movie.id)

    assert found is not None
    assert found.id == active.id
    assert await repository.find_movie_rating_by_user_and_movie(user.id, uuid4()) is None


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_tmdb_returns_active_row(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    deleted_rating = MovieRating(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=777,
        rating=5,
        review="Gone",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    active_rating = MovieRating(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        rating=8,
        review="Active",
    )
    await _add(seed_session, deleted_rating, active_rating)

    found = await repository.find_movie_rating_by_user_and_tmdb(user.id, movie.tmdb_id)

    assert found is not None
    assert found.id == active_rating.id
    assert await repository.find_movie_rating_by_user_and_tmdb(user.id, 777) is None
    assert await repository.find_movie_rating_by_user_and_tmdb(uuid4(), movie.tmdb_id) is None


@pytest.mark.asyncio
async def test_create_update_movie_rating_updates_existing_row_on_conflict(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    existing = MovieRating(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        rating=6,
        review="Initial",
    )
    await _add(seed_session, existing)

    updated = await repository.create_update_movie_rating(
        user_id=user.id,
        movie_id=movie.id,
        rating=10,
        comment="Updated",
        tmdb_id=movie.tmdb_id,
    )

    assert updated.id == existing.id
    assert updated.rating == 10
    assert updated.review == "Updated"


@pytest.mark.asyncio
async def test_create_update_movie_rating_revives_soft_deleted_row(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    deleted = MovieRating(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        rating=4,
        review="Old",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, deleted)

    revived = await repository.create_update_movie_rating(
        user_id=user.id,
        movie_id=movie.id,
        rating=9,
        comment="Back",
        tmdb_id=movie.tmdb_id,
    )

    assert revived.id == deleted.id
    assert revived.deleted is False
    assert revived.deleted_at is None
    assert revived.rating == 9
    assert revived.review == "Back"


@pytest.mark.asyncio
async def test_find_movie_ratings_by_user_and_movie_ids_filters_deleted_and_unknown(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie_a, movie_b = await _seed_fk_entities(seed_session)
    active = MovieRating(user_id=user.id, movie_id=movie_a.id, tmdb_id=movie_a.tmdb_id, rating=7, review="A")
    deleted = MovieRating(
        user_id=user.id,
        movie_id=movie_b.id,
        tmdb_id=movie_b.tmdb_id,
        rating=3,
        review="B",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)

    found = await repository.find_movie_ratings_by_user_and_movie_ids(user.id, {movie_a.id, movie_b.id, uuid4()})

    assert [rating.id for rating in found] == [active.id]


@pytest.mark.asyncio
async def test_find_movie_ratings_by_user_and_movie_ids_short_circuits_empty_set(
    repository: MovieRatingRepository,
):
    assert await repository.find_movie_ratings_by_user_and_movie_ids(uuid4(), set()) == []


@pytest.mark.asyncio
async def test_get_user_movie_ratings_average_excludes_deleted_and_null(
    repository: MovieRatingRepository,
    seed_session: AsyncSession,
):
    user, movie_a, movie_b = await _seed_fk_entities(seed_session)
    movie_c = Movie(tmdb_id=552, title="Movie C")
    movie_d = Movie(tmdb_id=553, title="Movie D")
    await _add(seed_session, movie_c, movie_d)

    rating_a = MovieRating(user_id=user.id, movie_id=movie_a.id, tmdb_id=movie_a.tmdb_id, rating=8, review="A")
    rating_b = MovieRating(user_id=user.id, movie_id=movie_b.id, tmdb_id=movie_b.tmdb_id, rating=6, review="B")
    deleted = MovieRating(
        user_id=user.id,
        movie_id=movie_c.id,
        tmdb_id=movie_c.tmdb_id,
        rating=10,
        review="Deleted",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    unrated = MovieRating(
        user_id=user.id,
        movie_id=movie_d.id,
        tmdb_id=movie_d.tmdb_id,
        rating=None,
        review="No score",
    )
    await _add(seed_session, rating_a, rating_b, deleted, unrated)

    stats = await repository.get_user_movie_ratings_average(user.id, {movie_a.id, movie_b.id, movie_c.id, movie_d.id})

    assert stats.average_rating == 7.0
    assert stats.total_ratings == 2


@pytest.mark.asyncio
async def test_get_user_movie_ratings_average_returns_zeroes_when_empty(
    repository: MovieRatingRepository,
):
    stats = await repository.get_user_movie_ratings_average(uuid4(), {uuid4()})

    assert stats.average_rating == 0.0
    assert stats.total_ratings == 0
