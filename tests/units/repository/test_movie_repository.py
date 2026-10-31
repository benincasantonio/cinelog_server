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
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.models.base_model import Base
from app.models.movie_model import Movie
from app.models.movie_provider_mapping_model import MovieProviderMapping
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
        await seed_session.refresh(movie, attribute_names=["providers", "updated_at", "title"])


@pytest.mark.asyncio
async def test_update_movie_changes_title_and_touches_updated_at(
    repository: MovieRepository, seed_session: AsyncSession
):
    movie = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="222")], title="Old")
    await _add(seed_session, movie)
    original_updated_at = movie.updated_at

    await repository.update_movie(movie.id, MovieUpdateRequest(title="New"))

    await seed_session.refresh(movie, attribute_names=["providers", "updated_at", "title"])
    assert movie.title == "New"
    assert movie.updated_at >= original_updated_at


@pytest.mark.asyncio
async def test_update_movie_is_silent_when_id_missing(repository: MovieRepository):
    await repository.update_movie(uuid4(), MovieUpdateRequest(title="Ghost"))


@pytest.mark.asyncio
async def test_update_movie_does_not_touch_soft_deleted_rows(repository: MovieRepository, seed_session: AsyncSession):
    deleted_movie = Movie(
        providers=[MovieProviderMapping(provider="tmdb", external_id="223")],
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
    active = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="333")], title="Active")
    deleted = Movie(
        providers=[MovieProviderMapping(provider="tmdb", external_id="334")],
        title="Gone",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)

    assert (await repository.find_movie_by_id(active.id)) is not None
    assert (await repository.find_movie_by_id(deleted.id)) is None
    assert (await repository.find_movie_by_id(uuid4())) is None


@pytest.mark.asyncio
async def test_find_movie_by_provider_matches_both_identity_fields_and_skips_deleted(
    repository: MovieRepository, seed_session: AsyncSession
):
    active = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="444")], title="Active")
    deleted = Movie(
        providers=[MovieProviderMapping(provider="tmdb", external_id="445")],
        title="Gone",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)

    found = await repository.find_movie_by_provider(MovieSourceReferenceDTO(source="tmdb", external_id="444"))
    assert found.id == active.id
    assert found.providers[0].external_id == "444"
    assert (await repository.find_movie_by_provider(MovieSourceReferenceDTO(source="other", external_id="444"))) is None
    assert (await repository.find_movie_by_provider(MovieSourceReferenceDTO(source="tmdb", external_id="445"))) is None
    assert (await repository.find_movie_by_provider(MovieSourceReferenceDTO(source="tmdb", external_id="9999"))) is None


@pytest.mark.asyncio
async def test_create_movie_persists_metadata_payload_and_sync_timestamp(
    repository: MovieRepository, seed_session: AsyncSession
):
    data = _import_data(555)
    movie = await repository.create_movie(data)

    assert movie.id is not None
    assert movie.deleted is False
    assert int(movie.providers[0].external_id) == 555

    persisted = await seed_session.get(Movie, movie.id, options=[selectinload(Movie.providers)])
    assert persisted is not None
    assert persisted.title == data.title
    assert persisted.release_date == datetime(2024, 1, 1)
    assert persisted.overview == data.overview
    assert persisted.poster_path == data.poster_path
    assert persisted.vote_average == data.vote_average
    assert persisted.runtime == data.runtime
    assert persisted.original_language == data.original_language
    assert persisted.providers[0].payload == data.source_payload
    assert persisted.providers[0].last_synced_at == OBSERVED_AT


@pytest.mark.asyncio
async def test_create_movie_returns_existing_on_duplicate_tmdb_id(
    repository: MovieRepository, seed_session: AsyncSession
):
    existing = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="666")], title="First")
    await _add(seed_session, existing)

    duplicate = await repository.create_movie(_import_data(666))

    assert duplicate.id == existing.id
    assert duplicate.providers[0].external_id == "666"
    assert duplicate.title == "First"


@pytest.mark.asyncio
async def test_create_movie_with_unknown_release_date_returns_none(
    repository: MovieRepository,
):
    movie = await repository.create_movie(_import_data(777, release_date=None))

    assert movie.release_date is None


@pytest.mark.asyncio
async def test_find_movies_by_ids_filters_deleted_and_unknown(repository: MovieRepository, seed_session: AsyncSession):
    a = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="801")], title="A")
    b = Movie(
        providers=[MovieProviderMapping(provider="tmdb", external_id="802")],
        title="B",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    c = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="803")], title="C")
    await _add(seed_session, a, b, c)

    found = await repository.find_movies_by_ids({a.id, b.id, c.id, uuid4()})

    assert {m.id for m in found} == {a.id, c.id}


@pytest.mark.asyncio
async def test_find_movies_by_ids_with_empty_set_short_circuits(repository: MovieRepository):
    assert await repository.find_movies_by_ids(set()) == []


@pytest.mark.asyncio
async def test_find_movies_by_ids_accepts_iterable(repository: MovieRepository, seed_session: AsyncSession):
    first = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="804")], title="First")
    second = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="805")], title="Second")
    await _add(seed_session, first, second)

    found = await repository.find_movies_by_ids([first.id, second.id])

    assert {movie.id for movie in found} == {first.id, second.id}


async def test_concurrent_imports_converge_on_one_uuid(session_factory, seed_session, monkeypatch):
    first_data = _import_data(901)
    second_data = _import_data(901)
    second_data.title = "Losing import"
    second_data.source_payload = {"different": "observation"}
    second_data.observed_at = datetime(2025, 1, 1, tzinfo=UTC)
    ready_to_commit = asyncio.Event()
    allow_commit = asyncio.Event()

    async with session_factory() as first_session, session_factory() as second_session:
        first_pid = await first_session.scalar(text("SELECT pg_backend_pid()"))
        second_pid = await second_session.scalar(text("SELECT pg_backend_pid()"))
        assert first_pid != second_pid
        original_commit = first_session.commit

        async def hold_first_commit():
            # The first mapping exists but stays uncommitted while the second import starts.
            ready_to_commit.set()
            await allow_commit.wait()
            await original_commit()

        monkeypatch.setattr(first_session, "commit", hold_first_commit)
        second_rollback = AsyncMock(wraps=second_session.rollback)
        monkeypatch.setattr(second_session, "rollback", second_rollback)
        sessions = iter((first_session, second_session))

        @asynccontextmanager
        async def session_provider():
            yield next(sessions)

        repository = MovieRepository(session_provider=session_provider)
        # Bound every wait and cancel/join both tasks before closing their sessions on failure.
        async with asyncio.timeout(10), asyncio.TaskGroup() as imports:
            first_task = imports.create_task(repository.create_movie(first_data))
            await ready_to_commit.wait()
            second_task = imports.create_task(repository.create_movie(second_data))
            while not await seed_session.scalar(
                text("SELECT :first_pid = ANY(pg_blocking_pids(:second_pid))"),
                {"first_pid": first_pid, "second_pid": second_pid},
            ):
                assert not second_task.done(), "The second import never waited on the first transaction"
                # Poll PostgreSQL's live lock state; elapsed time never releases the first commit.
                await asyncio.sleep(0.01)
            allow_commit.set()

        first, second = first_task.result(), second_task.result()
        second_rollback.assert_awaited_once()

    assert first.id == second.id
    assert first.title == second.title == first_data.title
    assert first.providers[0].payload == second.providers[0].payload == first_data.source_payload
    assert first.providers[0].last_synced_at == second.providers[0].last_synced_at == OBSERVED_AT
    assert await seed_session.scalar(select(func.count()).select_from(Movie)) == 1
    assert await seed_session.scalar(select(func.count()).select_from(MovieProviderMapping)) == 1


async def test_import_does_not_resurrect_a_soft_deleted_identity(repository, seed_session):
    existing = Movie(
        providers=[MovieProviderMapping(provider="tmdb", external_id="902")],
        title="Gone",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, existing)
    with pytest.raises(MovieIdentityUnavailableError, match="tmdb:902"):
        await repository.create_movie(_import_data(902))
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
    with pytest.raises(ValueError, match="currently enabled"):
        await repository.create_movie(data)


async def test_mapping_failure_rolls_back_candidate_movie(repository, seed_session):
    data = _import_data(905)
    data.source.external_id = "   "
    with pytest.raises(IntegrityError):
        await repository.create_movie(data)
    assert await seed_session.scalar(select(func.count()).select_from(Movie)) == 0
    assert await seed_session.scalar(select(func.count()).select_from(MovieProviderMapping)) == 0


async def test_retry_preserves_the_original_observation(repository, seed_session):
    first = await repository.create_movie(_import_data(906))
    retry = _import_data(906)
    retry.title = "New title"
    retry.source_payload = {"different": "observation"}
    retry.observed_at = datetime(2025, 1, 1, tzinfo=UTC)
    second = await repository.create_movie(retry)
    assert second.id == first.id
    assert second.title == first.title
    assert second.providers[0].payload == first.providers[0].payload
    assert second.providers[0].last_synced_at == OBSERVED_AT
    assert await seed_session.scalar(select(func.count()).select_from(Movie)) == 1


async def test_lookup_can_inspect_deleted_identity_without_releasing_it(repository, seed_session):
    movie = Movie(
        title="Removed",
        deleted=True,
        providers=[MovieProviderMapping(provider="tmdb", external_id="907")],
    )
    await _add(seed_session, movie)
    assert await repository.find_movie_by_provider(MovieSourceReferenceDTO(source="tmdb", external_id="907")) is None
    found = await repository.find_movie_by_provider(
        MovieSourceReferenceDTO(source="tmdb", external_id="907"), include_deleted=True
    )
    assert found.id == movie.id
    assert found.providers[0].last_synced_at is None


async def test_external_ids_remain_opaque_strings(repository):
    data = _import_data(908)
    # Storage has no numeric restriction; source adapters own format validation.
    data.source.external_id = str(uuid4())
    movie = await repository.create_movie(data)
    found = await repository.find_movie_by_provider(data.source)
    assert found.id == movie.id
    assert found.providers[0].external_id == data.source.external_id


async def test_batch_lookup_loads_mappings_in_a_bounded_number_of_queries(repository, pg_engine):
    movies = [await repository.create_movie(_import_data(910 + i)) for i in range(5)]
    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(pg_engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        found = await repository.find_movies_by_ids(movie.id for movie in movies)
        assert {movie.providers[0].external_id for movie in found} == {str(910 + i) for i in range(5)}
        assert len(statements) == 2
    finally:
        event.remove(pg_engine.sync_engine, "before_cursor_execute", record_statement)


async def test_find_movies_by_external_ids_maps_known_ids_including_deleted(repository, seed_session, pg_engine):
    active = Movie(providers=[MovieProviderMapping(provider="tmdb", external_id="930")], title="Active")
    deleted = Movie(
        providers=[MovieProviderMapping(provider="tmdb", external_id="931")],
        title="Gone",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)
    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(pg_engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        found = await repository.find_movies_by_external_ids("tmdb", ["930", "931", "932"])
    finally:
        event.remove(pg_engine.sync_engine, "before_cursor_execute", record_statement)

    assert {external_id: movie.id for external_id, movie in found.items()} == {"930": active.id, "931": deleted.id}
    assert found["931"].deleted is True
    assert len(statements) == 1
    assert await repository.find_movies_by_external_ids("other", ["930"]) == {}


async def test_find_movies_by_external_ids_with_no_ids_short_circuits(repository):
    assert await repository.find_movies_by_external_ids("tmdb", []) == {}


async def test_unrelated_error_is_not_swallowed_even_when_identity_exists(repository):
    await repository.create_movie(_import_data(920))
    data = _import_data(920)
    data.title = None  # type: ignore[assignment]
    with pytest.raises(IntegrityError):
        await repository.create_movie(data)
