"""PostgreSQL integration tests for ``FollowRepository``."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.user_follow_model import UserFollow
from app.models.user_model import User
from app.repository.follow_repository import FollowRepository


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    dbname = f"cinelog_follow_test_{uuid4().hex[:8]}"
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
        yield engine
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(pg_engine):
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def repository(session_factory):
    @asynccontextmanager
    async def provider():
        async with session_factory() as session:
            yield session

    return FollowRepository(provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _user(session: AsyncSession, suffix: str, *, deleted: bool = False) -> User:
    user = User(
        email=f"{suffix}@example.com",
        handle=suffix,
        first_name=suffix.title(),
        last_name="User",
        profile_visibility="public",
        deleted=deleted,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_concurrent_create_is_idempotent(repository, seed_session):
    follower = await _user(seed_session, "concurrent-follower")
    followed = await _user(seed_session, "concurrent-followed")

    await asyncio.gather(
        repository.create_follow(follower.id, followed.id),
        repository.create_follow(follower.id, followed.id),
    )

    count = await seed_session.scalar(select(func.count()).select_from(UserFollow))
    assert count == 1
    assert await repository.is_following(follower.id, followed.id) is True


@pytest.mark.asyncio
async def test_delete_is_idempotent(repository, seed_session):
    follower = await _user(seed_session, "delete-follower")
    followed = await _user(seed_session, "delete-followed")
    await repository.create_follow(follower.id, followed.id)

    await repository.delete_follow(follower.id, followed.id)
    await repository.delete_follow(follower.id, followed.id)

    assert await repository.is_following(follower.id, followed.id) is False


@pytest.mark.asyncio
async def test_summary_counts_directional_active_edges(repository, seed_session):
    profile = await _user(seed_session, "summary-profile")
    requester = await _user(seed_session, "summary-requester")
    other = await _user(seed_session, "summary-other")
    inactive = await _user(seed_session, "summary-inactive", deleted=True)

    await repository.create_follow(requester.id, profile.id)
    await repository.create_follow(other.id, profile.id)
    await repository.create_follow(profile.id, other.id)
    await repository.create_follow(inactive.id, profile.id)
    await repository.create_follow(profile.id, inactive.id)

    summary = await repository.get_follow_summary(profile.id, requester.id)

    assert summary.follower_count == 2
    assert summary.following_count == 1
    assert summary.is_following is True
    assert await repository.is_following(inactive.id, profile.id) is False
    assert await repository.is_following(profile.id, inactive.id) is False


@pytest.mark.asyncio
async def test_own_summary_never_reports_self_following(repository, seed_session):
    profile = await _user(seed_session, "own-summary")

    summary = await repository.get_follow_summary(profile.id, profile.id)

    assert summary.is_following is False


@pytest.mark.asyncio
async def test_database_rejects_self_follow(repository, seed_session):
    user = await _user(seed_session, "self-follow")

    with pytest.raises(IntegrityError):
        await repository.create_follow(user.id, user.id)


@pytest.mark.asyncio
async def test_hard_deleted_user_cascades_relationships(repository, seed_session):
    follower = await _user(seed_session, "cascade-follower")
    followed = await _user(seed_session, "cascade-followed")
    await repository.create_follow(follower.id, followed.id)

    await seed_session.execute(delete(User).where(User.id == followed.id))
    await seed_session.commit()

    count = await seed_session.scalar(select(func.count()).select_from(UserFollow))
    assert count == 0
