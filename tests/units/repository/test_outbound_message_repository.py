"""PostgreSQL integration tests for ``OutboundMessageRepository``."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.notification_model import Notification
from app.models.outbound_message_model import OutboundMessage
from app.models.user_model import User
from app.repository.outbound_message_repository import OutboundMessageRepository
from app.schemas.outbound_message_schemas import OutboundMessageCreateData
from app.types import NotificationType, OutboundMessageChannel, OutboundMessageKind, OutboundMessageStatus


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    dbname = f"cinelog_outbound_message_test_{uuid4().hex[:8]}"
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

    return OutboundMessageRepository(provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _add(session: AsyncSession, *entities) -> None:
    session.add_all(entities)
    await session.commit()
    for entity in entities:
        await session.refresh(entity)


async def _notification(session: AsyncSession, suffix: str) -> Notification:
    user = User(email=f"{suffix}@example.com", handle=suffix, first_name=suffix.title(), last_name="User")
    await _add(session, user)
    notification = Notification(
        recipient_id=user.id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="Title",
        body="Body",
    )
    await _add(session, notification)
    return notification


def _message(**overrides) -> OutboundMessage:
    defaults: dict[str, object] = {
        "kind": OutboundMessageKind.REGISTRATION_VERIFICATION.value,
        "channel": OutboundMessageChannel.EMAIL.value,
        "destination": "user@example.com",
        "subject": "Subject",
        "text_body": "text",
        "html_body": "<p>html</p>",
    }
    defaults.update(overrides)
    return OutboundMessage(**defaults)


def _create_data(
    *,
    kind: OutboundMessageKind = OutboundMessageKind.REGISTRATION_VERIFICATION,
    notification_id=None,
    channel: OutboundMessageChannel = OutboundMessageChannel.EMAIL,
    destination: str = "user@example.com",
    subject: str = "Subject",
    text_body: str = "Text body",
    html_body: str = "<p>HTML body</p>",
) -> OutboundMessageCreateData:
    return OutboundMessageCreateData(
        kind=kind,
        notification_id=notification_id,
        channel=channel,
        destination=destination,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_per_notification_and_channel_and_allows_repeated_null_notification_rows(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    notification = await _notification(seed_session, "enqueue")

    first_id = await repository.enqueue(
        _create_data(kind=OutboundMessageKind.NOTIFICATION, notification_id=notification.id)
    )
    duplicate_id = await repository.enqueue(
        _create_data(kind=OutboundMessageKind.NOTIFICATION, notification_id=notification.id)
    )
    auth_first_id = await repository.enqueue(_create_data(destination="auth-a@example.com"))
    auth_second_id = await repository.enqueue(_create_data(destination="auth-b@example.com"))

    assert first_id is not None
    assert duplicate_id is None
    assert auth_first_id is not None
    assert auth_second_id is not None
    assert auth_first_id != auth_second_id


@pytest.mark.asyncio
async def test_concurrent_duplicate_enqueue_returns_exactly_one_insert(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    notification = await _notification(seed_session, "concurrent-enqueue")
    data = _create_data(kind=OutboundMessageKind.NOTIFICATION, notification_id=notification.id)

    first, second = await asyncio.gather(repository.enqueue(data), repository.enqueue(data))

    results = [first, second]
    non_null_results = [result for result in results if result is not None]
    assert len(non_null_results) == 1


@pytest.mark.asyncio
async def test_enqueue_joins_a_caller_supplied_session_and_leaves_commit_to_the_caller(
    repository: OutboundMessageRepository,
    session_factory,
):
    async with session_factory() as session:
        message_id = await repository.enqueue(_create_data(destination="joined@example.com"), session=session)
        assert message_id is not None
        await session.rollback()

    async with session_factory() as verify_session:
        result = await verify_session.execute(
            select(OutboundMessage).where(OutboundMessage.destination == "joined@example.com")
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_claim_pending_messages_filters_orders_and_maps_fields(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    now = datetime.now(UTC)
    due_earlier = _message(
        destination="earlier@example.com", subject="Earlier", available_at=now - timedelta(minutes=2)
    )
    due_later = _message(
        kind=OutboundMessageKind.PASSWORD_RESET.value,
        destination="later@example.com",
        subject="Later",
        available_at=now - timedelta(minutes=1),
    )
    not_yet_due = _message(destination="future@example.com", available_at=now + timedelta(minutes=5))
    already_processing = _message(
        destination="processing@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        available_at=now - timedelta(minutes=3),
    )
    already_delivered = _message(
        destination="delivered@example.com",
        text_body=None,
        html_body=None,
        status=OutboundMessageStatus.DELIVERED.value,
        available_at=now - timedelta(minutes=3),
    )
    await _add(seed_session, due_earlier, due_later, not_yet_due, already_processing, already_delivered)
    due_earlier_id, due_later_id = due_earlier.id, due_later.id

    claimed = await repository.claim_pending_messages(OutboundMessageChannel.EMAIL, batch_size=10)

    assert [message.id for message in claimed] == [due_earlier_id, due_later_id]
    first = claimed[0]
    assert first.kind == OutboundMessageKind.REGISTRATION_VERIFICATION.value
    assert first.channel == OutboundMessageChannel.EMAIL.value
    assert first.destination == "earlier@example.com"
    assert first.subject == "Earlier"
    assert first.text_body == "text"
    assert first.html_body == "<p>html</p>"
    assert first.attempt_count == 1

    seed_session.expire_all()
    persisted = (
        await seed_session.execute(select(OutboundMessage).where(OutboundMessage.id == due_earlier_id))
    ).scalar_one()
    assert persisted.status == OutboundMessageStatus.PROCESSING.value
    assert persisted.locked_at is not None
    assert persisted.attempt_count == 1


@pytest.mark.asyncio
async def test_claim_pending_messages_respects_batch_size(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    messages = [_message(destination=f"batch-{index}@example.com") for index in range(5)]
    await _add(seed_session, *messages)

    claimed = await repository.claim_pending_messages(OutboundMessageChannel.EMAIL, batch_size=2)

    assert len(claimed) == 2


@pytest.mark.asyncio
async def test_claim_pending_messages_skips_rows_locked_by_another_session(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
    session_factory,
):
    locked = _message(destination="locked@example.com")
    free = _message(destination="free@example.com")
    await _add(seed_session, locked, free)

    async with session_factory() as locking_session:
        await locking_session.execute(select(OutboundMessage).where(OutboundMessage.id == locked.id).with_for_update())

        claimed = await repository.claim_pending_messages(OutboundMessageChannel.EMAIL, batch_size=10)

        assert [message.id for message in claimed] == [free.id]

        await locking_session.rollback()


@pytest.mark.asyncio
async def test_two_concurrent_claims_never_overlap(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    messages = [_message(destination=f"gather-{index}@example.com") for index in range(6)]
    await _add(seed_session, *messages)

    first_batch, second_batch = await asyncio.gather(
        repository.claim_pending_messages(OutboundMessageChannel.EMAIL, batch_size=6),
        repository.claim_pending_messages(OutboundMessageChannel.EMAIL, batch_size=6),
    )

    first_ids = {message.id for message in first_batch}
    second_ids = {message.id for message in second_batch}

    assert first_ids.isdisjoint(second_ids)
    assert first_ids | second_ids == {message.id for message in messages}


@pytest.mark.asyncio
async def test_mark_delivered_clears_bodies_and_sets_delivered_at(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    message = _message(
        destination="deliver@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        locked_at=datetime.now(UTC),
    )
    await _add(seed_session, message)
    message_id = message.id

    await repository.mark_delivered(message_id)

    seed_session.expire_all()
    persisted = (
        await seed_session.execute(select(OutboundMessage).where(OutboundMessage.id == message_id))
    ).scalar_one()
    assert persisted.status == OutboundMessageStatus.DELIVERED.value
    assert persisted.delivered_at is not None
    assert persisted.locked_at is None
    assert persisted.last_error is None
    assert persisted.text_body is None
    assert persisted.html_body is None


@pytest.mark.asyncio
async def test_schedule_retry_sets_future_available_at_and_retains_bodies(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    message = _message(
        destination="retry@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        locked_at=datetime.now(UTC),
        attempt_count=1,
    )
    await _add(seed_session, message)
    message_id = message.id
    before = datetime.now(UTC)

    await repository.schedule_retry(message_id, delay=timedelta(seconds=60), failure_detail="boom")

    seed_session.expire_all()
    persisted = (
        await seed_session.execute(select(OutboundMessage).where(OutboundMessage.id == message_id))
    ).scalar_one()
    assert persisted.status == OutboundMessageStatus.PENDING.value
    assert persisted.locked_at is None
    assert persisted.last_error == "boom"
    assert persisted.text_body == "text"
    assert persisted.html_body == "<p>html</p>"
    expected_available_at = before + timedelta(seconds=60)
    assert abs((persisted.available_at - expected_available_at).total_seconds()) < 5


@pytest.mark.asyncio
async def test_mark_failed_clears_bodies_and_sets_last_error(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    message = _message(
        destination="fail@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        locked_at=datetime.now(UTC),
        attempt_count=5,
    )
    await _add(seed_session, message)
    message_id = message.id

    await repository.mark_failed(message_id, failure_detail="exhausted")

    seed_session.expire_all()
    persisted = (
        await seed_session.execute(select(OutboundMessage).where(OutboundMessage.id == message_id))
    ).scalar_one()
    assert persisted.status == OutboundMessageStatus.FAILED.value
    assert persisted.locked_at is None
    assert persisted.last_error == "exhausted"
    assert persisted.text_body is None
    assert persisted.html_body is None


@pytest.mark.asyncio
async def test_recover_stale_locks_requeues_fails_and_leaves_fresh_locks_untouched(
    repository: OutboundMessageRepository,
    seed_session: AsyncSession,
):
    now = datetime.now(UTC)
    stale_requeueable = _message(
        destination="stale-requeue@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        locked_at=now - timedelta(seconds=600),
        attempt_count=1,
    )
    stale_exhausted = _message(
        destination="stale-exhausted@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        locked_at=now - timedelta(seconds=600),
        attempt_count=5,
    )
    fresh_lock = _message(
        destination="fresh@example.com",
        status=OutboundMessageStatus.PROCESSING.value,
        locked_at=now - timedelta(seconds=5),
        attempt_count=1,
    )
    await _add(seed_session, stale_requeueable, stale_exhausted, fresh_lock)
    stale_requeueable_id = stale_requeueable.id
    stale_exhausted_id = stale_exhausted.id
    fresh_lock_id = fresh_lock.id

    result = await repository.recover_stale_locks(lock_timeout=timedelta(seconds=300), max_attempts=5)

    assert result.requeued == 1
    assert result.failed == 1

    seed_session.expire_all()
    persisted = {
        row.id: row
        for row in (
            await seed_session.execute(
                select(OutboundMessage).where(
                    OutboundMessage.id.in_([stale_requeueable_id, stale_exhausted_id, fresh_lock_id])
                )
            )
        )
        .scalars()
        .all()
    }

    requeued_row = persisted[stale_requeueable_id]
    assert requeued_row.status == OutboundMessageStatus.PENDING.value
    assert requeued_row.locked_at is None

    exhausted_row = persisted[stale_exhausted_id]
    assert exhausted_row.status == OutboundMessageStatus.FAILED.value
    assert exhausted_row.locked_at is None
    assert exhausted_row.text_body is None
    assert exhausted_row.html_body is None

    fresh_row = persisted[fresh_lock_id]
    assert fresh_row.status == OutboundMessageStatus.PROCESSING.value
    assert fresh_row.locked_at is not None
