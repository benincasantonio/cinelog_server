"""PostgreSQL integration tests for ``NotificationUnitOfWork``."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.notification_model import Notification
from app.models.outbound_message_model import OutboundMessage
from app.models.user_model import User
from app.repository.notification_repository import NotificationRepository
from app.repository.notification_unit_of_work import NotificationUnitOfWork
from app.repository.outbound_message_repository import OutboundMessageRepository
from app.repository.user_repository import UserRepository
from app.schemas.notification_schemas import NotificationCreateData
from app.services.outbound_message_service import OutboundMessageService
from app.types import NotificationType, OutboundMessageKind, OutboundMessageStatus


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    dbname = f"cinelog_notification_uow_test_{uuid4().hex[:8]}"
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
async def unit_of_work(session_factory):
    @asynccontextmanager
    async def provider():
        async with session_factory() as session:
            yield session

    notification_repository = NotificationRepository(provider)
    outbound_message_repository = OutboundMessageRepository(provider)
    user_repository = UserRepository(provider)
    outbound_message_service = OutboundMessageService(outbound_message_repository, user_repository)
    return NotificationUnitOfWork(notification_repository, outbound_message_service, provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


async def _user(session: AsyncSession, suffix: str) -> User:
    user = User(email=f"{suffix}@example.com", handle=suffix, first_name=suffix.title(), last_name="User")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _create_data(recipient_id, *, key: str | None = "event-key") -> NotificationCreateData:
    return NotificationCreateData(
        recipient_id=recipient_id,
        type=NotificationType.FOLLOW_STARTED,
        title="Someone followed you",
        body="A user started following you.",
        deduplication_key=key,
    )


@pytest.mark.asyncio
async def test_create_notification_with_deliveries_commits_notification_and_message_together(
    unit_of_work: NotificationUnitOfWork,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "committed-recipient")
    recipient_email = recipient.email
    data = _create_data(recipient.id)

    result = await unit_of_work.create_notification_with_deliveries(data)

    assert result.created is True
    notification_id, notification_title = result.notification.id, result.notification.title
    seed_session.expire_all()
    message = (
        await seed_session.execute(select(OutboundMessage).where(OutboundMessage.notification_id == notification_id))
    ).scalar_one()
    assert message.kind == OutboundMessageKind.NOTIFICATION.value
    assert message.destination == recipient_email
    assert message.subject == notification_title
    assert message.status == OutboundMessageStatus.PENDING.value


@pytest.mark.asyncio
async def test_a_failing_enqueue_rolls_back_the_notification_too(
    unit_of_work: NotificationUnitOfWork,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "rollback-recipient")
    data = _create_data(recipient.id)

    with (
        patch.dict("app.services.outbound_email_renderer._NOTIFICATION_RENDERERS", clear=True),
        pytest.raises(ValueError, match="No email renderer registered"),
    ):
        await unit_of_work.create_notification_with_deliveries(data)

    seed_session.expire_all()
    notification_count = (await seed_session.execute(select(func.count(Notification.id)))).scalar_one()
    message_count = (await seed_session.execute(select(func.count(OutboundMessage.id)))).scalar_one()
    assert notification_count == 0
    assert message_count == 0


@pytest.mark.asyncio
async def test_deduplicated_second_call_yields_exactly_one_notification_and_message(
    unit_of_work: NotificationUnitOfWork,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "dedup-recipient")
    data = _create_data(recipient.id, key="dedup-event")

    first = await unit_of_work.create_notification_with_deliveries(data)
    second = await unit_of_work.create_notification_with_deliveries(data)

    assert first.created is True
    assert second.created is False
    assert first.notification.id == second.notification.id

    seed_session.expire_all()
    notification_count = (await seed_session.execute(select(func.count(Notification.id)))).scalar_one()
    message_count = (await seed_session.execute(select(func.count(OutboundMessage.id)))).scalar_one()
    assert notification_count == 1
    assert message_count == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_creation_yields_exactly_one_notification_and_message(
    unit_of_work: NotificationUnitOfWork,
    seed_session: AsyncSession,
):
    recipient = await _user(seed_session, "concurrent-recipient")
    data = _create_data(recipient.id, key="concurrent-event")

    first, second = await asyncio.gather(
        unit_of_work.create_notification_with_deliveries(data),
        unit_of_work.create_notification_with_deliveries(data),
    )

    assert {first.created, second.created} == {True, False}
    assert first.notification.id == second.notification.id

    seed_session.expire_all()
    notification_count = (await seed_session.execute(select(func.count(Notification.id)))).scalar_one()
    message_count = (await seed_session.execute(select(func.count(OutboundMessage.id)))).scalar_one()
    assert notification_count == 1
    assert message_count == 1
