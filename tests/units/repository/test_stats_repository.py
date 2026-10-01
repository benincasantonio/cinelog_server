"""Unit tests for the PostgreSQL ``StatsRepository`` read model."""

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
from app.models.log_model import Log
from app.models.movie_model import Movie
from app.models.movie_rating_model import MovieRating
from app.models.user_model import User
from app.repository.stats_repository import StatsRepository
from app.schemas.stats_schemas import StatsByMethod


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    dbname = f"cinelog_stats_test_{uuid4().hex[:8]}"

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
def repository(session_factory) -> StatsRepository:
    @asynccontextmanager
    async def _provider():
        async with session_factory() as session:
            yield session

    return StatsRepository(session_provider=_provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _add(seed_session: AsyncSession, *entities) -> None:
    seed_session.add_all(entities)
    await seed_session.commit()
    for entity in entities:
        await seed_session.refresh(entity)


def _user(suffix: str) -> User:
    return User(
        email=f"stats-{suffix}@example.com",
        handle=f"stats-{suffix}",
        first_name="Stats",
        last_name="User",
        date_of_birth=date(1990, 1, 1),
    )


def _log(
    user: User,
    movie: Movie,
    watched_at: datetime,
    watched_where: str,
    **kwargs,
) -> Log:
    return Log(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=watched_at,
        watched_where=watched_where,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_get_user_stats_returns_zeroed_aggregate_for_empty_user(repository: StatsRepository):
    stats = await repository.get_user_stats(uuid4())

    assert stats.total_watches == 0
    assert stats.unique_titles == 0
    assert stats.total_minutes == 0
    assert stats.vote_average is None
    assert stats.by_method == StatsByMethod(cinema=0, streaming=0, home_video=0, tv=0, other=0)


@pytest.mark.asyncio
async def test_get_user_stats_aggregates_runtime_per_watch_and_ratings_per_title(
    repository: StatsRepository,
    seed_session: AsyncSession,
):
    user = _user("owner")
    other_user = _user("other")
    movie_a = Movie(tmdb_id=101, title="Movie A", runtime=120)
    movie_b = Movie(tmdb_id=102, title="Movie B", runtime=90)
    await _add(seed_session, user, other_user, movie_a, movie_b)

    await _add(
        seed_session,
        _log(user, movie_a, datetime(2024, 1, 1, tzinfo=UTC), "cinema"),
        _log(user, movie_a, datetime(2024, 2, 1, tzinfo=UTC), "streaming"),
        _log(user, movie_b, datetime(2024, 3, 1, tzinfo=UTC), "homeVideo"),
        _log(other_user, movie_a, datetime(2024, 4, 1, tzinfo=UTC), "tv"),
        MovieRating(user_id=user.id, movie_id=movie_a.id, tmdb_id=movie_a.tmdb_id, rating=8),
        MovieRating(user_id=user.id, movie_id=movie_b.id, tmdb_id=movie_b.tmdb_id, rating=6),
        MovieRating(user_id=other_user.id, movie_id=movie_a.id, tmdb_id=movie_a.tmdb_id, rating=10),
    )

    stats = await repository.get_user_stats(user.id)

    assert stats.total_watches == 3
    assert stats.unique_titles == 2
    assert stats.total_minutes == 330
    assert stats.vote_average == 7.0
    assert stats.by_method == StatsByMethod(cinema=1, streaming=1, home_video=1, tv=0, other=0)


@pytest.mark.asyncio
async def test_get_user_stats_applies_inclusive_date_range(
    repository: StatsRepository,
    seed_session: AsyncSession,
):
    user = _user("dates")
    movie = Movie(tmdb_id=201, title="Date Movie", runtime=100)
    await _add(seed_session, user, movie)
    await _add(
        seed_session,
        _log(user, movie, datetime(2023, 12, 31, 23, 59, tzinfo=UTC), "other"),
        _log(user, movie, datetime(2024, 1, 1, tzinfo=UTC), "cinema"),
        _log(user, movie, datetime(2024, 12, 31, 23, 59, tzinfo=UTC), "tv"),
        _log(user, movie, datetime(2025, 1, 1, tzinfo=UTC), "streaming"),
    )

    stats = await repository.get_user_stats(
        user.id,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 12, 31),
    )

    assert stats.total_watches == 2
    assert stats.unique_titles == 1
    assert stats.total_minutes == 200
    assert stats.by_method == StatsByMethod(cinema=1, streaming=0, home_video=0, tv=1, other=0)


@pytest.mark.asyncio
async def test_get_user_stats_excludes_soft_deleted_rows_and_handles_missing_runtime(
    repository: StatsRepository,
    seed_session: AsyncSession,
):
    user = _user("deleted")
    active_movie = Movie(tmdb_id=301, title="Active", runtime=100)
    deleted_movie = Movie(
        tmdb_id=302,
        title="Deleted",
        runtime=200,
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    null_runtime_movie = Movie(tmdb_id=303, title="Unknown Runtime", runtime=None)
    await _add(seed_session, user, active_movie, deleted_movie, null_runtime_movie)
    await _add(
        seed_session,
        _log(user, active_movie, datetime(2024, 1, 1, tzinfo=UTC), "cinema"),
        _log(user, deleted_movie, datetime(2024, 1, 2, tzinfo=UTC), "streaming"),
        _log(user, null_runtime_movie, datetime(2024, 1, 3, tzinfo=UTC), "other"),
        _log(
            user,
            active_movie,
            datetime(2024, 1, 4, tzinfo=UTC),
            "tv",
            deleted=True,
            deleted_at=datetime.now(UTC),
        ),
        MovieRating(
            user_id=user.id,
            movie_id=active_movie.id,
            tmdb_id=active_movie.tmdb_id,
            rating=9,
            deleted=True,
            deleted_at=datetime.now(UTC),
        ),
    )

    stats = await repository.get_user_stats(user.id)

    assert stats.total_watches == 3
    assert stats.unique_titles == 3
    assert stats.total_minutes == 100
    assert stats.vote_average is None
    assert stats.by_method == StatsByMethod(cinema=1, streaming=1, home_video=0, tv=0, other=1)
