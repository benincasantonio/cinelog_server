"""Unit tests for ``MovieRepository``.

A real PostgreSQL instance is spawned per test session by ``pytest-postgresql``
(via ``pg_ctl``), and a fresh database is created/dropped per test by
``DatabaseJanitor``. SQLAlchemy async sessions connect to that database through
``asyncpg``; the repository's ``session_provider`` seam is used to inject the
test session without monkeypatching module globals.

The host needs PostgreSQL binaries available on ``PATH`` (``brew install
postgresql@16`` on macOS, ``apt-get install postgresql`` on Debian/Ubuntu).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.movie_model import Movie
from app.repository.movie_repository import MovieRepository
from app.schemas.movie_schemas import MovieCreateRequest, MovieUpdateRequest
from app.schemas.tmdb_schemas import TMDBMovieDetails


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    """Create a fresh database per test and return an async SQLAlchemy engine."""
    dbname = f"cinelog_test_{uuid4().hex[:8]}"

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
def repository(session_factory) -> MovieRepository:
    @asynccontextmanager
    async def _provider():
        async with session_factory() as session:
            yield session

    return MovieRepository(session_provider=_provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


def _tmdb_details(tmdb_id: int, *, release_date: str | None = "2024-01-01") -> TMDBMovieDetails:
    return TMDBMovieDetails(
        id=tmdb_id,
        title=f"Movie {tmdb_id}",
        original_title=f"Movie {tmdb_id} Original",
        release_date=release_date,
        overview=f"Overview {tmdb_id}",
        poster_path=f"/{tmdb_id}.jpg",
        backdrop_path=None,
        vote_average=7.5,
        vote_count=100,
        runtime=120,
        budget=10,
        revenue=100,
        status="Released",
        tagline=None,
        homepage=None,
        imdb_id=None,
        original_language="en",
        popularity=10.0,
        adult=False,
        genres=[],
        production_companies=[],
        production_countries=[],
        spoken_languages=[],
    )


async def _add(seed_session: AsyncSession, *movies: Movie) -> None:
    seed_session.add_all(movies)
    await seed_session.commit()
    for movie in movies:
        await seed_session.refresh(movie)


@pytest.mark.asyncio
async def test_create_movie_persists_row(repository: MovieRepository, seed_session: AsyncSession):
    movie = await repository.create_movie(MovieCreateRequest(title="Inception", tmdb_id=111))

    assert movie.id is not None
    assert movie.title == "Inception"
    assert movie.tmdb_id == 111
    assert movie.deleted is False

    persisted = await seed_session.get(Movie, movie.id)
    assert persisted is not None
    assert persisted.title == "Inception"


@pytest.mark.asyncio
async def test_update_movie_changes_title_and_touches_updated_at(
    repository: MovieRepository, seed_session: AsyncSession
):
    movie = Movie(tmdb_id=222, title="Old")
    await _add(seed_session, movie)
    original_updated_at = movie.updated_at

    await repository.update_movie(movie.id, MovieUpdateRequest(title="New"))

    await seed_session.refresh(movie)
    assert movie.title == "New"
    assert movie.updated_at >= original_updated_at


@pytest.mark.asyncio
async def test_update_movie_is_silent_when_id_missing(repository: MovieRepository):
    await repository.update_movie(uuid4(), MovieUpdateRequest(title="Ghost"))


@pytest.mark.asyncio
async def test_update_movie_does_not_touch_soft_deleted_rows(repository: MovieRepository, seed_session: AsyncSession):
    deleted_movie = Movie(
        tmdb_id=223,
        title="Original",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, deleted_movie)

    await repository.update_movie(deleted_movie.id, MovieUpdateRequest(title="Resurrected"))

    await seed_session.refresh(deleted_movie)
    assert deleted_movie.title == "Original"
    assert deleted_movie.deleted is True


@pytest.mark.asyncio
async def test_find_movie_by_id_returns_active_row(repository: MovieRepository, seed_session: AsyncSession):
    active = Movie(tmdb_id=333, title="Active")
    deleted = Movie(tmdb_id=334, title="Gone", deleted=True, deleted_at=datetime.now(UTC))
    await _add(seed_session, active, deleted)

    assert (await repository.find_movie_by_id(active.id)) is not None
    assert (await repository.find_movie_by_id(deleted.id)) is None
    assert (await repository.find_movie_by_id(uuid4())) is None


@pytest.mark.asyncio
async def test_find_movie_by_tmdb_id_skips_soft_deleted(repository: MovieRepository, seed_session: AsyncSession):
    active = Movie(tmdb_id=444, title="Active")
    deleted = Movie(tmdb_id=445, title="Gone", deleted=True, deleted_at=datetime.now(UTC))
    await _add(seed_session, active, deleted)

    assert (await repository.find_movie_by_tmdb_id(444)) is not None
    assert (await repository.find_movie_by_tmdb_id(445)) is None
    assert (await repository.find_movie_by_tmdb_id(9999)) is None


@pytest.mark.asyncio
async def test_create_from_tmdb_data_persists_payload_and_sync_timestamp(
    repository: MovieRepository, seed_session: AsyncSession
):
    movie = await repository.create_from_tmdb_data(_tmdb_details(555))

    assert movie.tmdb_id == 555
    assert movie.release_date == datetime(2024, 1, 1)
    assert movie.tmdb_payload is not None
    assert movie.tmdb_payload["id"] == 555
    assert movie.tmdb_last_synced_at is not None

    persisted = await seed_session.get(Movie, movie.id)
    assert persisted is not None
    assert persisted.tmdb_payload is not None


@pytest.mark.asyncio
async def test_create_from_tmdb_data_returns_existing_on_duplicate_tmdb_id(
    repository: MovieRepository, seed_session: AsyncSession
):
    existing = Movie(tmdb_id=666, title="First")
    await _add(seed_session, existing)

    duplicate = await repository.create_from_tmdb_data(_tmdb_details(666))

    assert duplicate.id == existing.id
    assert duplicate.tmdb_id == 666


@pytest.mark.asyncio
async def test_create_from_tmdb_data_with_invalid_release_date_returns_none(
    repository: MovieRepository,
):
    movie = await repository.create_from_tmdb_data(_tmdb_details(777, release_date="not-a-date"))

    assert movie.release_date is None


@pytest.mark.asyncio
async def test_find_movies_by_ids_filters_deleted_and_unknown(repository: MovieRepository, seed_session: AsyncSession):
    a = Movie(tmdb_id=801, title="A")
    b = Movie(tmdb_id=802, title="B", deleted=True, deleted_at=datetime.now(UTC))
    c = Movie(tmdb_id=803, title="C")
    await _add(seed_session, a, b, c)

    found = await repository.find_movies_by_ids({a.id, b.id, c.id, uuid4()})

    assert {m.id for m in found} == {a.id, c.id}


@pytest.mark.asyncio
async def test_find_movies_by_ids_with_empty_set_short_circuits(repository: MovieRepository):
    assert await repository.find_movies_by_ids(set()) == []


@pytest.mark.asyncio
async def test_find_movies_by_ids_accepts_iterable(repository: MovieRepository, seed_session: AsyncSession):
    first = Movie(tmdb_id=804, title="First")
    second = Movie(tmdb_id=805, title="Second")
    await _add(seed_session, first, second)

    found = await repository.find_movies_by_ids([first.id, second.id])

    assert {movie.id for movie in found} == {first.id, second.id}


@pytest.mark.asyncio
async def test_get_movie_stats_sums_runtime_excluding_deleted(repository: MovieRepository, seed_session: AsyncSession):
    a = Movie(tmdb_id=901, title="A", runtime=120)
    b = Movie(tmdb_id=902, title="B", runtime=90)
    deleted = Movie(tmdb_id=903, title="C", runtime=999, deleted=True, deleted_at=datetime.now(UTC))
    null_runtime = Movie(tmdb_id=904, title="D", runtime=None)
    await _add(seed_session, a, b, deleted, null_runtime)

    stats = await repository.get_movie_stats({a.id, b.id, deleted.id, null_runtime.id})

    assert stats.total_runtime == 210


@pytest.mark.asyncio
async def test_get_movie_stats_accepts_iterable(repository: MovieRepository, seed_session: AsyncSession):
    first = Movie(tmdb_id=905, title="First", runtime=100)
    second = Movie(tmdb_id=906, title="Second", runtime=80)
    await _add(seed_session, first, second)

    stats = await repository.get_movie_stats((first.id, second.id))

    assert stats.total_runtime == 180


@pytest.mark.asyncio
async def test_get_movie_stats_with_empty_set_short_circuits(repository: MovieRepository):
    stats = await repository.get_movie_stats(set())

    assert stats.total_runtime == 0
