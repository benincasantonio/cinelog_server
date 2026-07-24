"""PostgreSQL integration tests for ``NotificationRepository``."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import event, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.notification_model import Notification
from app.models.user_model import User
from app.repository.notification_repository import NotificationRepository
from app.schemas.notification_schemas import NotificationCreateData
from app.types import NotificationType, TimestampUUIDCursor


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    dbname = f"cinelog_notification_test_{uuid4().hex[:8]}"
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
    return async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def repository(session_factory):
    @asynccontextmanager
    async def provider():
        async with session_factory() as session:
            yield session

    return NotificationRepository(provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _add(session: AsyncSession, *entities) -> None:
    session.add_all(entities)
    await session.commit()
    for entity in entities:
        await session.refresh(entity)


async def _user(session: AsyncSession, suffix: str, *, deleted: bool = False) -> User:
    user = User(
        email=f"{suffix}@example.com",
        handle=suffix,
        first_name=suffix.title(),
        last_name="User",
        deleted=deleted,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    await _add(session, user)
    return user


def _create_data(recipient_id, *, actor_id=None, key="event-key") -> NotificationCreateData:
    return NotificationCreateData(
        recipient_id=recipient_id,
        actor_id=actor_id,
        type=NotificationType.FOLLOW_STARTED,
        title="Someone followed you",
        body="A user started following you.",
        deduplication_key=key,
    )


@pytest.mark.asyncio
async def test_create_notification_is_idempotent_per_recipient_and_reuses_soft_deleted_keys(
    repository: NotificationRepository,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "create-recipient")
    other = await _user(seed_session, "create-other")

    first = await repository.create_notification(_create_data(recipient.id))
    duplicate = await repository.create_notification(_create_data(recipient.id))
    other_recipient = await repository.create_notification(_create_data(other.id))
    no_key_first = await repository.create_notification(_create_data(recipient.id, key=None))
    no_key_second = await repository.create_notification(_create_data(recipient.id, key=None))

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.notification.id == first.notification.id
    assert other_recipient.created is True
    assert no_key_first.notification.id != no_key_second.notification.id

    await seed_session.execute(
        update(Notification).where(Notification.id == first.notification.id).values(deleted=True)
    )
    await seed_session.commit()
    replacement = await repository.create_notification(_create_data(recipient.id))

    assert replacement.created is True
    assert replacement.notification.id != first.notification.id


@pytest.mark.asyncio
async def test_concurrent_duplicate_creation_returns_one_notification(
    repository: NotificationRepository,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "concurrent-recipient")
    request = _create_data(recipient.id, key="concurrent-event")

    first, second = await asyncio.gather(
        repository.create_notification(request),
        repository.create_notification(request),
    )

    assert {first.created, second.created} == {True, False}
    assert first.notification.id == second.notification.id


@pytest.mark.asyncio
async def test_list_notifications_is_stable_scoped_and_does_not_mark_rows_read(
    repository: NotificationRepository,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "list-recipient")
    other = await _user(seed_session, "list-other")
    actor = await _user(seed_session, "list-actor")
    deleted_actor = await _user(seed_session, "list-deleted-actor", deleted=True)
    timestamp = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    older = Notification(
        recipient_id=recipient.id,
        actor_id=actor.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Older",
        body="Older body",
        created_at=timestamp - timedelta(minutes=1),
        updated_at=timestamp - timedelta(minutes=1),
    )
    tied_first = Notification(
        id=uuid4(),
        recipient_id=recipient.id,
        actor_id=deleted_actor.id,
        type=NotificationType.FOLLOW_REQUESTED.value,
        title="Tied first",
        body="Tied first body",
        created_at=timestamp,
        updated_at=timestamp,
    )
    tied_second = Notification(
        id=uuid4(),
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_ACCEPTED.value,
        title="Tied second",
        body="Tied second body",
        read_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    foreign = Notification(
        recipient_id=other.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Foreign",
        body="Foreign body",
    )
    deleted = Notification(
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Deleted",
        body="Deleted body",
        deleted=True,
        deleted_at=timestamp,
    )
    await _add(seed_session, older, tied_first, tied_second, foreign, deleted)

    expected_tied = sorted([tied_first, tied_second], key=lambda item: item.id, reverse=True)
    first_page = await repository.list_notifications(recipient.id, unread_only=False, limit=2, cursor=None)
    second_page = await repository.list_notifications(
        recipient.id,
        unread_only=False,
        limit=2,
        cursor=TimestampUUIDCursor(
            timestamp=first_page.items[-1].created_at,
            id=first_page.items[-1].id,
        ),
    )
    unread_page = await repository.list_notifications(recipient.id, unread_only=True, limit=100, cursor=None)

    assert [item.id for item in first_page.items] == [item.id for item in expected_tied]
    assert [item.id for item in second_page.items] == [older.id]
    assert first_page.has_more is True
    assert second_page.has_more is False
    assert first_page.unread_count == 2
    assert unread_page.unread_count == 2
    assert {item.id for item in unread_page.items} == {older.id, tied_first.id}
    assert first_page.items[0].read_at == expected_tied[0].read_at
    assert first_page.items[1].read_at == expected_tied[1].read_at

    loaded_by_id = {item.id: item for item in [*first_page.items, *second_page.items]}
    assert loaded_by_id[older.id].actor.handle == actor.handle
    assert loaded_by_id[tied_first.id].actor.deleted is True


@pytest.mark.asyncio
async def test_listing_uses_fixed_query_count_for_batched_actor_loading(
    repository: NotificationRepository,
    seed_session: AsyncSession,
    pg_engine,
):
    recipient = await _user(seed_session, "query-recipient")
    actors = [await _user(seed_session, f"query-actor-{index}") for index in range(5)]
    await _add(
        seed_session,
        *[
            Notification(
                recipient_id=recipient.id,
                actor_id=actor.id,
                type=NotificationType.FOLLOW_STARTED.value,
                title="Title",
                body="Body",
            )
            for actor in actors
        ],
    )
    statements: list[str] = []

    def record_query(*args):
        statements.append(args[2])

    event.listen(pg_engine.sync_engine, "before_cursor_execute", record_query)
    try:
        page = await repository.list_notifications(recipient.id, unread_only=False, limit=20, cursor=None)
    finally:
        event.remove(pg_engine.sync_engine, "before_cursor_execute", record_query)

    assert len(page.items) == 5
    assert len(statements) == 3


@pytest.mark.asyncio
async def test_mark_notification_read_is_server_owned_scoped_and_idempotent(
    repository: NotificationRepository,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "read-recipient")
    other = await _user(seed_session, "read-other")
    notification = Notification(
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Unread",
        body="Unread body",
    )
    await _add(seed_session, notification)
    before = datetime.now(UTC)

    first = await repository.mark_notification_read(notification.id, recipient.id)
    repeated = await repository.mark_notification_read(notification.id, recipient.id)
    foreign = await repository.mark_notification_read(notification.id, other.id)

    assert first is not None
    assert repeated is not None
    assert first.read_at is not None
    assert before <= first.read_at <= datetime.now(UTC)
    assert repeated.read_at == first.read_at
    assert foreign is None


@pytest.mark.asyncio
async def test_mark_all_notifications_read_uses_one_timestamp_and_preserves_existing_state(
    repository: NotificationRepository,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "bulk-recipient")
    other = await _user(seed_session, "bulk-other")
    old_read_at = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)
    unread_a = Notification(
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Unread A",
        body="Body",
    )
    unread_b = Notification(
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_REQUESTED.value,
        title="Unread B",
        body="Body",
    )
    already_read = Notification(
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_ACCEPTED.value,
        title="Read",
        body="Body",
        read_at=old_read_at,
    )
    foreign = Notification(
        recipient_id=other.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Foreign",
        body="Body",
    )
    deleted = Notification(
        recipient_id=recipient.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Deleted",
        body="Body",
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, unread_a, unread_b, already_read, foreign, deleted)
    unread_a_id = unread_a.id
    unread_b_id = unread_b.id
    already_read_id = already_read.id
    foreign_id = foreign.id
    deleted_id = deleted.id
    notification_ids = [unread_a_id, unread_b_id, already_read_id, foreign_id, deleted_id]

    first = await repository.mark_all_notifications_read(recipient.id)
    repeated = await repository.mark_all_notifications_read(recipient.id)
    seed_session.expire_all()
    persisted = {
        item.id: item
        for item in (await seed_session.execute(select(Notification).where(Notification.id.in_(notification_ids))))
        .scalars()
        .all()
    }

    assert first.updated_count == 2
    assert first.unread_count == 0
    assert repeated.updated_count == 0
    assert repeated.unread_count == 0
    assert persisted[unread_a_id].read_at == persisted[unread_b_id].read_at
    assert persisted[already_read_id].read_at == old_read_at
    assert persisted[foreign_id].read_at is None
    assert persisted[deleted_id].read_at is None
