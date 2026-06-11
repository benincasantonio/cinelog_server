"""Unit tests for ``PostgresLogRepository``."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.log_model import PostgresLog
from app.models.movie_model import PostgresMovie
from app.models.user_model import PostgresUser
from app.repository.postgres_log_repository import PostgresLogRepository
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest
from app.schemas.stats_schemas import LogStats


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    """Create a fresh database per test and return an async SQLAlchemy engine."""
    dbname = f"cinelog_log_test_{uuid4().hex[:8]}"

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
def repository(session_factory) -> PostgresLogRepository:
    @asynccontextmanager
    async def _provider():
        async with session_factory() as session:
            yield session

    return PostgresLogRepository(session_provider=_provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _add(seed_session: AsyncSession, *entities) -> None:
    seed_session.add_all(entities)
    await seed_session.commit()
    for entity in entities:
        await seed_session.refresh(entity)


async def _seed_fk_entities(seed_session: AsyncSession) -> tuple[PostgresUser, PostgresMovie, PostgresMovie]:
    user = PostgresUser(
        email="logs@example.com",
        handle="logs-user",
        first_name="Logs",
        last_name="User",
        date_of_birth=date(1990, 1, 1),
    )
    movie_a = PostgresMovie(tmdb_id=550, title="Fight Club")
    movie_b = PostgresMovie(tmdb_id=551, title="Alien")
    await _add(seed_session, user, movie_a, movie_b)
    return user, movie_a, movie_b


def _create_request(
    movie_id: UUID,
    *,
    tmdb_id: int,
    date_watched: date = date(2024, 1, 2),
    watched_where: str = "cinema",
    viewing_notes: str | None = "Great watch",
    poster_path: str | None = "/poster.jpg",
) -> LogCreateRequest:
    return LogCreateRequest(
        movie_id=movie_id,
        tmdb_id=tmdb_id,
        date_watched=date_watched,
        viewing_notes=viewing_notes,
        poster_path=poster_path,
        watched_where=watched_where,
    )


@pytest.mark.asyncio
async def test_create_log_persists_row(repository: PostgresLogRepository, seed_session: AsyncSession):
    user, movie, _ = await _seed_fk_entities(seed_session)

    log = await repository.create_log(
        user.id,
        _create_request(movie.id, tmdb_id=movie.tmdb_id),
    )

    assert log.id is not None
    assert log.user_id == user.id
    assert log.movie_id == movie.id
    assert log.tmdb_id == movie.tmdb_id
    assert log.date_watched == datetime(2024, 1, 2, tzinfo=UTC)
    assert log.watched_where == "cinema"
    assert log.deleted is False


@pytest.mark.asyncio
async def test_find_log_by_id_respects_owner_and_deleted_rows(
    repository: PostgresLogRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    other_user = PostgresUser(
        email="other@example.com",
        handle="other-user",
        first_name="Other",
        last_name="User",
        date_of_birth=date(1991, 1, 1),
    )
    await _add(seed_session, other_user)

    active = PostgresLog(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        watched_where="cinema",
    )
    deleted = PostgresLog(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=999,
        date_watched=datetime(2024, 1, 3, tzinfo=UTC),
        watched_where="streaming",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)

    assert (await repository.find_log_by_id(active.id, user.id)) is not None
    assert await repository.find_log_by_id(active.id, other_user.id) is None
    assert await repository.find_log_by_id(deleted.id, user.id) is None


@pytest.mark.asyncio
async def test_update_log_applies_partial_updates_and_rejects_wrong_owner(
    repository: PostgresLogRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    other_user = PostgresUser(
        email="update-other@example.com",
        handle="update-other",
        first_name="Update",
        last_name="Other",
        date_of_birth=date(1991, 2, 1),
    )
    await _add(seed_session, other_user)

    log = PostgresLog(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        viewing_notes="Before",
        watched_where="cinema",
    )
    await _add(seed_session, log)

    updated = await repository.update_log(
        log.id,
        user.id,
        LogUpdateRequest(
            viewing_notes="After",
            watched_where="streaming",
            date_watched=date(2024, 1, 5),
        ),
    )

    assert updated is not None
    assert updated.viewing_notes == "After"
    assert updated.watched_where == "streaming"
    assert updated.date_watched == datetime(2024, 1, 5, tzinfo=UTC)

    assert await repository.update_log(log.id, other_user.id, LogUpdateRequest(viewing_notes="Nope")) is None


@pytest.mark.asyncio
async def test_delete_log_hard_deletes_row(repository: PostgresLogRepository, seed_session: AsyncSession):
    user, movie, _ = await _seed_fk_entities(seed_session)
    other_user = PostgresUser(
        email="delete-other@example.com",
        handle="delete-other",
        first_name="Delete",
        last_name="Other",
        date_of_birth=date(1992, 1, 1),
    )
    await _add(seed_session, other_user)
    other_user_id = other_user.id

    log = PostgresLog(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        watched_where="cinema",
    )
    await _add(seed_session, log)
    log_id = log.id
    user_id = user.id

    deleted = await repository.delete_log(log_id, user_id)

    assert deleted is not None
    assert deleted.id == log_id
    seed_session.expire_all()
    assert await seed_session.get(PostgresLog, log_id) is None
    assert await repository.delete_log(log_id, user_id) is None
    assert await repository.delete_log(uuid4(), other_user_id) is None


@pytest.mark.asyncio
async def test_find_logs_by_user_id_filters_and_sorts(
    repository: PostgresLogRepository,
    seed_session: AsyncSession,
):
    user, movie_a, movie_b = await _seed_fk_entities(seed_session)
    other_user = PostgresUser(
        email="filters-other@example.com",
        handle="filters-other",
        first_name="Filters",
        last_name="Other",
        date_of_birth=date(1992, 2, 2),
    )
    await _add(seed_session, other_user)

    older_streaming = PostgresLog(
        user_id=user.id,
        movie_id=movie_a.id,
        tmdb_id=movie_a.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        viewing_notes="Older",
        watched_where="streaming",
        created_at=datetime(2024, 1, 2, 8, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 8, 0, tzinfo=UTC),
    )
    newer_streaming = PostgresLog(
        user_id=user.id,
        movie_id=movie_b.id,
        tmdb_id=movie_b.tmdb_id,
        date_watched=datetime(2024, 1, 3, tzinfo=UTC),
        viewing_notes="Newer",
        watched_where="streaming",
        created_at=datetime(2024, 1, 2, 20, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 20, 0, tzinfo=UTC),
    )
    cinema = PostgresLog(
        user_id=user.id,
        movie_id=movie_a.id,
        tmdb_id=movie_a.tmdb_id,
        date_watched=datetime(2024, 1, 4, tzinfo=UTC),
        viewing_notes="Cinema",
        watched_where="cinema",
        created_at=datetime(2024, 1, 4, 9, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, 9, 0, tzinfo=UTC),
    )
    other_users_log = PostgresLog(
        user_id=other_user.id,
        movie_id=movie_b.id,
        tmdb_id=movie_b.tmdb_id,
        date_watched=datetime(2024, 1, 5, tzinfo=UTC),
        watched_where="tv",
    )
    deleted = PostgresLog(
        user_id=user.id,
        movie_id=movie_b.id,
        tmdb_id=999,
        date_watched=datetime(2024, 1, 6, tzinfo=UTC),
        watched_where="tv",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, older_streaming, newer_streaming, cinema, other_users_log, deleted)

    no_filters = await repository.find_logs_by_user_id(user.id)
    assert [log.id for log in no_filters] == [cinema.id, newer_streaming.id, older_streaming.id]

    watched_where_only = await repository.find_logs_by_user_id(user.id, watched_where="streaming")
    assert [log.id for log in watched_where_only] == [newer_streaming.id, older_streaming.id]

    date_filtered = await repository.find_logs_by_user_id(
        user.id,
        date_watched_from=date(2024, 1, 3),
        date_watched_to=date(2024, 1, 4),
    )
    assert [log.id for log in date_filtered] == [cinema.id, newer_streaming.id]

    date_sort_asc = await repository.find_logs_by_user_id(user.id, sort_by="dateWatched", sort_order="asc")
    assert [log.id for log in date_sort_asc] == [older_streaming.id, newer_streaming.id, cinema.id]

    watched_where_sort_asc = await repository.find_logs_by_user_id(user.id, sort_by="watchedWhere", sort_order="asc")
    assert [log.id for log in watched_where_sort_asc] == [cinema.id, older_streaming.id, newer_streaming.id]

    watched_where_sort_desc = await repository.find_logs_by_user_id(
        user.id,
        sort_by="watchedWhere",
        sort_order="desc",
    )
    assert [log.id for log in watched_where_sort_desc] == [newer_streaming.id, older_streaming.id, cinema.id]


@pytest.mark.asyncio
async def test_find_logs_by_movie_id_supports_optional_user_filter_and_created_order(
    repository: PostgresLogRepository,
    seed_session: AsyncSession,
):
    user, movie, _ = await _seed_fk_entities(seed_session)
    other_user = PostgresUser(
        email="movie-filter@example.com",
        handle="movie-filter",
        first_name="Movie",
        last_name="Filter",
        date_of_birth=date(1993, 3, 3),
    )
    await _add(seed_session, other_user)

    first = PostgresLog(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        watched_where="cinema",
        created_at=datetime(2024, 1, 2, 8, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 8, 0, tzinfo=UTC),
    )
    second = PostgresLog(
        user_id=user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=datetime(2024, 1, 3, tzinfo=UTC),
        watched_where="streaming",
        created_at=datetime(2024, 1, 2, 20, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, 20, 0, tzinfo=UTC),
    )
    other_users_log = PostgresLog(
        user_id=other_user.id,
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        date_watched=datetime(2024, 1, 4, tzinfo=UTC),
        watched_where="tv",
    )
    await _add(seed_session, first, second, other_users_log)

    all_logs = await repository.find_logs_by_movie_id(movie.id)
    assert [log.id for log in all_logs] == [first.id, second.id, other_users_log.id]

    user_logs = await repository.find_logs_by_movie_id(movie.id, user.id)
    assert [log.id for log in user_logs] == [first.id, second.id]

    assert await repository.find_logs_by_movie_id(uuid4()) == []


@pytest.mark.asyncio
async def test_get_log_stats_returns_summary_distribution_and_uuid_movie_ids(
    repository: PostgresLogRepository,
    seed_session: AsyncSession,
):
    user, movie_a, movie_b = await _seed_fk_entities(seed_session)
    movie_c = PostgresMovie(tmdb_id=552, title="Movie C")
    await _add(seed_session, movie_c)

    active_one = PostgresLog(
        user_id=user.id,
        movie_id=movie_a.id,
        tmdb_id=movie_a.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        watched_where="cinema",
    )
    active_two = PostgresLog(
        user_id=user.id,
        movie_id=movie_a.id,
        tmdb_id=movie_a.tmdb_id,
        date_watched=datetime(2024, 1, 3, tzinfo=UTC),
        watched_where="streaming",
    )
    active_three = PostgresLog(
        user_id=user.id,
        movie_id=movie_b.id,
        tmdb_id=movie_b.tmdb_id,
        date_watched=datetime(2024, 1, 4, tzinfo=UTC),
        watched_where="streaming",
    )
    deleted = PostgresLog(
        user_id=user.id,
        movie_id=movie_c.id,
        tmdb_id=movie_c.tmdb_id,
        date_watched=datetime(2024, 1, 5, tzinfo=UTC),
        watched_where="tv",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active_one, active_two, active_three, deleted)

    stats = await repository.get_log_stats(user.id)

    assert stats.total_watches == 3
    assert stats.unique_titles == 2
    assert set(stats.unique_movie_ids) == {movie_a.id, movie_b.id}
    assert {entry.watched_where: entry.count for entry in stats.distribution} == {
        "cinema": 1,
        "streaming": 2,
    }


@pytest.mark.asyncio
async def test_get_log_stats_supports_date_range_and_empty_result(
    repository: PostgresLogRepository,
    seed_session: AsyncSession,
):
    user, movie_a, movie_b = await _seed_fk_entities(seed_session)
    first = PostgresLog(
        user_id=user.id,
        movie_id=movie_a.id,
        tmdb_id=movie_a.tmdb_id,
        date_watched=datetime(2024, 1, 2, tzinfo=UTC),
        watched_where="cinema",
    )
    second = PostgresLog(
        user_id=user.id,
        movie_id=movie_b.id,
        tmdb_id=movie_b.tmdb_id,
        date_watched=datetime(2024, 2, 2, tzinfo=UTC),
        watched_where="streaming",
    )
    await _add(seed_session, first, second)

    january_stats = await repository.get_log_stats(
        user.id,
        date_from=date(2024, 1, 1),
        date_to=date(2024, 1, 31),
    )
    assert january_stats.total_watches == 1
    assert january_stats.unique_titles == 1
    assert january_stats.unique_movie_ids == [movie_a.id]

    empty_stats = await repository.get_log_stats(
        user.id,
        date_from=date(2024, 3, 1),
        date_to=date(2024, 3, 31),
    )
    assert empty_stats == LogStats()
