"""PostgreSQL integration tests for ``FollowRepository``."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import delete, func, literal, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.notification_model import Notification
from app.models.user_follow_model import UserFollow
from app.models.user_model import User
from app.repository.follow_repository import FollowRepository
from app.repository.notification_repository import NotificationRepository
from app.repository.user_repository import UserRepository
from app.schemas.notification_schemas import NotificationCreateData
from app.services.follow_service import FollowService
from app.types import NotificationType
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


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
def session_provider(session_factory):
    @asynccontextmanager
    async def provider():
        async with session_factory() as session:
            yield session

    return provider


@pytest.fixture
def repository(session_provider):
    return FollowRepository(session_provider)


@pytest.fixture
def notifications(session_provider):
    return NotificationRepository(session_provider)


@pytest.fixture
def service(repository, notifications, session_provider):
    return FollowService(UserRepository(session_provider), repository, notifications, session_provider)


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

    created = await asyncio.gather(
        repository.create_follow(follower.id, followed.id),
        repository.create_follow(follower.id, followed.id),
    )

    count = await seed_session.scalar(select(func.count()).select_from(UserFollow))
    assert count == 1
    assert sorted(created) == [False, True]
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


async def _counts(session_factory):
    async with session_factory() as session:
        return (
            await session.scalar(select(func.count()).select_from(UserFollow)),
            await session.scalar(select(func.count()).select_from(Notification)),
        )


def _notification_data(follower, target, **kwargs):
    return NotificationCreateData(
        recipient_id=target.id,
        actor_id=follower.id,
        type=NotificationType.FOLLOW_STARTED,
        title="New follower",
        body="Started following you.",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_caller_owned_session_keeps_both_writes_uncommitted(
    repository, notifications, seed_session, session_factory
):
    follower = await _user(seed_session, "owned-follower")
    target = await _user(seed_session, "owned-target")
    async with session_factory() as session:
        async with session.begin():
            assert await repository.create_follow(follower.id, target.id, session=session)
            result = await notifications.create_notification(_notification_data(follower, target), session=session)
            assert result.created
            assert session.in_transaction()
            assert await _counts(session_factory) == (0, 0)
        assert await _counts(session_factory) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["follow", "notification", "commit"])
async def test_failed_transaction_rolls_back_both_writes_and_retry_succeeds(
    service, repository, notifications, seed_session, session_factory, pg_engine, monkeypatch, failure
):
    follower = await _user(seed_session, "rollback-follower")
    target = await _user(seed_session, "rollback-target")
    if failure == "commit":
        async with pg_engine.begin() as connection:
            await connection.execute(
                text("""
                CREATE FUNCTION reject_test_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'injected commit failure'; END $$
            """)
            )
            await connection.execute(
                text("""
                CREATE CONSTRAINT TRIGGER reject_test_commit AFTER INSERT ON notifications
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_test_commit()
            """)
            )
    else:
        owner = repository if failure == "follow" else notifications
        name = "create_follow" if failure == "follow" else "create_notification"
        original = getattr(owner, name)

        async def fail_after_write(*args, session, **kwargs):
            await original(*args, session=session, **kwargs)
            await session.execute(text("SELECT 1 / 0"))

        monkeypatch.setattr(owner, name, fail_after_write)

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(follower.id, target.handle)
    assert exc_info.value.error is ErrorCodes.ERROR_CREATING_FOLLOW
    assert await _counts(session_factory) == (0, 0)

    if failure == "commit":
        async with pg_engine.begin() as connection:
            await connection.execute(text("DROP TRIGGER reject_test_commit ON notifications"))
            await connection.execute(text("DROP FUNCTION reject_test_commit()"))
    else:
        monkeypatch.setattr(owner, name, original)

    result = await service.follow_user(follower.id, target.handle)
    assert result.created is True
    assert await _counts(session_factory) == (1, 1)
    # Discarding a successful response must not change retry behavior.
    assert await service.follow_user(follower.id, target.handle) is None
    assert await _counts(session_factory) == (1, 1)


@pytest.mark.asyncio
async def test_existing_relationship_without_notification_is_not_backfilled(
    service, repository, seed_session, session_factory
):
    follower = await _user(seed_session, "legacy-follower")
    target = await _user(seed_session, "legacy-target")
    await repository.create_follow(follower.id, target.id)

    assert await service.follow_user(follower.id, target.handle) is None
    assert await _counts(session_factory) == (1, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("history_age", [None, 1, 8])
async def test_concurrent_follow_workflow_has_one_winner(
    service, repository, seed_session, session_factory, monkeypatch, history_age
):
    follower = await _user(seed_session, "race-follower")
    target = await _user(seed_session, "race-target")
    if history_age is not None:
        await service.follow_user(follower.id, target.handle)
        await service.unfollow_user(follower.id, target.handle)
        await seed_session.execute(update(Notification).values(created_at=func.now() - timedelta(days=history_age)))
        await seed_session.commit()
    barrier = asyncio.Barrier(2)
    original = repository.create_follow

    async def synchronized_insert(*args, **kwargs):
        await barrier.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(repository, "create_follow", synchronized_insert)
    async with asyncio.timeout(10):
        results = await asyncio.gather(
            service.follow_user(follower.id, target.handle),
            service.follow_user(follower.id, target.handle),
        )
    assert sum(result is not None and result.created for result in results) == (0 if history_age == 1 else 1)
    assert await _counts(session_factory) == (1, 2 if history_age == 8 else 1)


@pytest.mark.asyncio
async def test_unfollow_overlapping_uncommitted_follow_does_not_split_notification(
    service, notifications, seed_session, session_factory, monkeypatch
):
    follower = await _user(seed_session, "overlap-follower")
    target = await _user(seed_session, "overlap-target")
    inserted, release = asyncio.Event(), asyncio.Event()
    original = notifications.create_notification

    async def hold_notification(*args, **kwargs):
        result = await original(*args, **kwargs)
        inserted.set()
        await release.wait()
        return result

    monkeypatch.setattr(notifications, "create_notification", hold_notification)
    async with asyncio.timeout(10), asyncio.TaskGroup() as group:
        follow = group.create_task(service.follow_user(follower.id, target.handle))
        await inserted.wait()
        assert await _counts(session_factory) == (0, 0)
        # The pending insert is invisible, so this delete linearizes before the follow.
        await service.unfollow_user(follower.id, target.handle)
        release.set()
    assert follow.result().created
    assert await _counts(session_factory) == (1, 1)
    await service.unfollow_user(follower.id, target.handle)
    assert await service.follow_user(follower.id, target.handle) is None
    assert await _counts(session_factory) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(("age_seconds", "expected"), [(604799.999999, True), (604800, False), (604800.000001, False)])
async def test_cooldown_exact_database_time_boundary(
    notifications, seed_session, session_factory, age_seconds, expected
):
    follower = await _user(seed_session, "boundary-follower")
    target = await _user(seed_session, "boundary-target")
    async with session_factory() as session, session.begin():
        result = await notifications.create_notification(_notification_data(follower, target), session=session)
        await session.execute(
            update(Notification)
            .where(Notification.id == result.notification.id)
            .values(created_at=func.now() - timedelta(seconds=age_seconds))
        )
        assert await notifications.has_recent_follow_started(target.id, follower.id, session=session) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unread", "read", "deleted"])
async def test_retained_history_suppresses_refollow_without_redis_and_does_not_reset_window(
    service, notifications, seed_session, session_factory, state
):
    follower = await _user(seed_session, "retained-follower")
    target = await _user(seed_session, "retained-target")
    result = await notifications.create_notification(
        _notification_data(follower, target, deduplication_key=f"follow.started:{follower.id}:2025-W52")
    )
    await seed_session.execute(
        update(Notification)
        .where(Notification.id == result.notification.id)
        .values(
            created_at=func.now() - timedelta(days=6),
            read_at=func.now() if state == "read" else None,
            deleted=state == "deleted",
            deleted_at=func.now() if state == "deleted" else None,
        )
    )
    await seed_session.commit()
    original_time = await seed_session.scalar(select(Notification.created_at))
    with patch("app.infrastructure.redis.RedisClient.get_instance", side_effect=RuntimeError("Redis unavailable")):
        assert await service.follow_user(follower.id, target.handle) is None
        await service.unfollow_user(follower.id, target.handle)
        assert await service.follow_user(follower.id, target.handle) is None
    assert await _counts(session_factory) == (1, 1)
    assert await seed_session.scalar(select(Notification.created_at)) == original_time

    await seed_session.execute(update(Notification).values(created_at=func.now() - timedelta(days=8)))
    await seed_session.commit()
    await service.unfollow_user(follower.id, target.handle)
    emitted = await service.follow_user(follower.id, target.handle)
    assert emitted.created
    assert await _counts(session_factory) == (1, 2)


@pytest.mark.asyncio
async def test_cooldown_is_scoped_to_actor_recipient_and_notification_type(
    service, notifications, seed_session, session_factory
):
    follower = await _user(seed_session, "scope-follower")
    target = await _user(seed_session, "scope-target")
    other = await _user(seed_session, "scope-other")
    await notifications.create_notification(_notification_data(other, target))
    await notifications.create_notification(_notification_data(follower, other))
    data = _notification_data(follower, target).model_copy(update={"type": NotificationType.FOLLOW_ACCEPTED})
    await notifications.create_notification(data)

    assert (await service.follow_user(follower.id, target.handle)).created
    assert await _counts(session_factory) == (1, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("previous", "current"),
    [
        (datetime(2026, 11, 1, 23, 59, tzinfo=UTC), datetime(2026, 11, 2, 0, 1, tzinfo=UTC)),
        (datetime(2025, 12, 28, 23, 59, tzinfo=UTC), datetime(2026, 1, 1, 0, 1, tzinfo=UTC)),
    ],
)
async def test_cooldown_ignores_iso_week_and_year_boundaries(
    service, notifications, seed_session, session_factory, monkeypatch, previous, current
):
    follower = await _user(seed_session, "calendar-follower")
    target = await _user(seed_session, "calendar-target")
    assert previous.strftime("%G-W%V") != current.strftime("%G-W%V")
    await notifications.create_notification(
        _notification_data(follower, target, deduplication_key=f"follow.started:{follower.id}:{previous:%G-W%V}")
    )
    await seed_session.execute(update(Notification).values(created_at=previous))
    await seed_session.commit()
    # Bind a fixed database timestamp so calendar regression coverage works year-round.
    monkeypatch.setattr("app.repository.notification_repository.func", SimpleNamespace(now=lambda: literal(current)))

    assert await service.follow_user(follower.id, target.handle) is None
    assert await _counts(session_factory) == (1, 1)
