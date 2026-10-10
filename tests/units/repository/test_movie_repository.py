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

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.movie_model import Movie
from app.repository.movie_repository import MovieRepository
from app.repository.movie_repository_protocol import MovieIdentityUnavailableError
from app.schemas.movie_import_schemas import MovieCreateDTO
from app.schemas.movie_provider_schemas import MovieSourceReferenceDTO
from app.schemas.movie_schemas import MovieUpdateRequest


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


OBSERVED_AT = datetime(2024, 1, 1, 10, tzinfo=UTC)


def _import_data(external_id: int, *, release_date: date | None = date(2024, 1, 1)) -> MovieCreateDTO:
    return MovieCreateDTO(
        source=MovieSourceReferenceDTO(source="tmdb", external_id=str(external_id)),
        title=f"Movie {external_id}",
        release_date=release_date,
        overview=f"Overview {external_id}",
        poster_path=f"/{external_id}.jpg",
        vote_average=7.5,
        runtime=120,
        original_language="en",
        observed_at=OBSERVED_AT,
        source_payload={"opaque": "snapshot", "id": "not a canonical UUID"},
    )


async def _add(seed_session: AsyncSession, *movies: Movie) -> None:
    seed_session.add_all(movies)
    await seed_session.commit()
    for movie in movies:
        await seed_session.refresh(movie)


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
async def test_create_movie_persists_metadata_payload_and_sync_timestamp(
    repository: MovieRepository, seed_session: AsyncSession
):
    data = _import_data(555)
    movie = await repository.create_movie(data)

    assert movie.id is not None
    assert movie.deleted is False
    assert movie.tmdb_id == 555

    persisted = await seed_session.get(Movie, movie.id)
    assert persisted is not None
    assert persisted.title == data.title
    assert persisted.release_date == datetime(2024, 1, 1)
    assert persisted.overview == data.overview
    assert persisted.poster_path == data.poster_path
    assert persisted.vote_average == data.vote_average
    assert persisted.runtime == data.runtime
    assert persisted.original_language == data.original_language
    assert persisted.tmdb_payload == data.source_payload
    assert persisted.tmdb_last_synced_at == OBSERVED_AT


@pytest.mark.asyncio
async def test_create_movie_returns_existing_on_duplicate_tmdb_id(
    repository: MovieRepository, seed_session: AsyncSession
):
    existing = Movie(tmdb_id=666, title="First")
    await _add(seed_session, existing)

    duplicate = await repository.create_movie(_import_data(666))

    assert duplicate.id == existing.id
    assert duplicate.tmdb_id == 666
    assert duplicate.title == "First"


@pytest.mark.asyncio
async def test_create_movie_with_unknown_release_date_returns_none(
    repository: MovieRepository,
):
    movie = await repository.create_movie(_import_data(777, release_date=None))

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


async def test_concurrent_imports_converge_on_one_uuid(repository):
    first, second = await asyncio.gather(
        repository.create_movie(_import_data(901)),
        repository.create_movie(_import_data(901)),
    )
    assert first.id == second.id
    assert first.tmdb_last_synced_at == second.tmdb_last_synced_at == OBSERVED_AT


async def test_import_does_not_resurrect_a_soft_deleted_identity(repository, seed_session):
    existing = Movie(tmdb_id=902, title="Gone", deleted=True, deleted_at=datetime.now(UTC))
    await _add(seed_session, existing)
    with pytest.raises(MovieIdentityUnavailableError, match="tmdb:902") as error:
        await repository.create_movie(_import_data(902))
    assert isinstance(error.value.__cause__, IntegrityError)
    await seed_session.refresh(existing)
    assert existing.deleted is True
    assert existing.title == "Gone"


async def test_import_reraises_integrity_errors_unrelated_to_the_source_identity(repository):
    data = _import_data(904)
    data.title = None  # type: ignore[assignment]

    with pytest.raises(IntegrityError):
        await repository.create_movie(data)


async def test_legacy_storage_rejects_an_unsupported_source(repository):
    data = _import_data(903)
    data.source.source = "unsupported"
    with pytest.raises(ValueError, match="current storage schema"):
        await repository.create_movie(data)
