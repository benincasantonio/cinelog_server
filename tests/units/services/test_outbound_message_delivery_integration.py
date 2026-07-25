"""End-to-end delivery cycle tests against a real PostgreSQL outbox.

The rest of the delivery-service tests mock the repository, which proves the service
calls the right method but not that a row actually lands in the right state. These drive
``run_once()`` through the real repository so the success, retry, exhausted, expiry and
settlement-failure paths are verified as persisted state.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.outbound_message_config import OutboundMessageWorkerConfig
from app.models.base_model import Base
from app.models.notification_model import Notification  # noqa: F401  (registers the FK target)
from app.models.outbound_message_model import OutboundMessage
from app.models.user_model import User  # noqa: F401  (registers the FK target)
from app.repository.outbound_message_repository import OutboundMessageRepository
from app.services.email_service import EmailDeliveryError
from app.services.outbound_message_delivery_service import OutboundMessageDeliveryService
from app.types import OutboundMessageChannel, OutboundMessageKind, OutboundMessageStatus


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    dbname = f"cinelog_delivery_test_{uuid4().hex[:8]}"
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


@pytest.fixture
def email_service():
    return MagicMock()


def _worker_config(**overrides) -> OutboundMessageWorkerConfig:
    defaults: dict[str, int] = {
        "batch_size": 10,
        "poll_interval": 5,
        "lock_timeout": 300,
        "max_attempts": 5,
        "retry_base_delay": 60,
        "retry_max_delay": 3600,
        "delivered_retention_days": 30,
        "failed_retention_days": 90,
        "purge_interval": 0,
    }
    defaults.update(overrides)
    return OutboundMessageWorkerConfig(**defaults)


@pytest.fixture
def service(repository, email_service):
    return OutboundMessageDeliveryService(
        outbound_message_repository=repository,
        email_service=email_service,
        worker_config=_worker_config(),
    )


async def _seed(session: AsyncSession, **overrides) -> OutboundMessage:
    defaults: dict[str, object] = {
        "kind": OutboundMessageKind.PASSWORD_RESET.value,
        "channel": OutboundMessageChannel.EMAIL.value,
        "destination": "user@example.com",
        "subject": "Password Reset - Cinelog",
        "text_body": "Your code is ABC123",
        "html_body": "<p>Your code is ABC123</p>",
    }
    defaults.update(overrides)
    message = OutboundMessage(**defaults)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def _reload(session: AsyncSession, message_id) -> OutboundMessage:
    session.expire_all()
    return (await session.execute(select(OutboundMessage).where(OutboundMessage.id == message_id))).scalar_one()


@pytest.mark.asyncio
async def test_successful_cycle_delivers_and_clears_the_body(service, seed_session, email_service):
    message = await _seed(seed_session)
    message_id = message.id

    processed = await service.run_once()

    assert processed == 1
    email_service.send_transactional_email.assert_called_once()
    persisted = await _reload(seed_session, message_id)
    assert persisted.status == OutboundMessageStatus.DELIVERED.value
    assert persisted.delivered_at is not None
    assert persisted.attempt_count == 1
    assert persisted.text_body is None
    assert persisted.lock_token is None


@pytest.mark.asyncio
async def test_transport_failure_schedules_a_backed_off_retry_and_keeps_the_body(service, seed_session, email_service):
    message = await _seed(seed_session)
    message_id = message.id
    email_service.send_transactional_email.side_effect = EmailDeliveryError("smtp refused the connection")

    await service.run_once()

    persisted = await _reload(seed_session, message_id)
    assert persisted.status == OutboundMessageStatus.PENDING.value
    assert persisted.attempt_count == 1
    assert persisted.available_at > datetime.now(UTC) + timedelta(seconds=30)
    assert persisted.text_body == "Your code is ABC123"
    assert "smtp refused" in persisted.last_error


@pytest.mark.asyncio
async def test_final_attempt_fails_terminally(service, seed_session, email_service):
    message = await _seed(seed_session, attempt_count=4)
    message_id = message.id
    email_service.send_transactional_email.side_effect = EmailDeliveryError("smtp still refusing")

    await service.run_once()

    persisted = await _reload(seed_session, message_id)
    assert persisted.status == OutboundMessageStatus.FAILED.value
    assert persisted.attempt_count == 5
    assert persisted.text_body is None


@pytest.mark.asyncio
async def test_message_expiring_after_claim_is_retired_without_sending(
    service, repository, seed_session, email_service, monkeypatch
):
    """A code valid at claim time can be dead by the time its turn to send arrives.

    Deliveries within a batch are serial, so the check that decides is the one taken
    immediately before the message is handed to SMTP, not the one at claim time.
    """

    message = await _seed(seed_session, expires_at=datetime.now(UTC) + timedelta(minutes=15))
    message_id = message.id

    claimed = await repository.claim_pending_messages(OutboundMessageChannel.EMAIL, batch_size=10)
    assert len(claimed) == 1

    # The message waits behind earlier sends until its code expires.
    await seed_session.execute(
        update(OutboundMessage)
        .where(OutboundMessage.id == message_id)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await seed_session.commit()

    async def already_claimed(*_args, **_kwargs):
        return claimed

    monkeypatch.setattr(repository, "claim_pending_messages", already_claimed)

    await service.run_once()

    persisted = await _reload(seed_session, message_id)
    assert persisted.status == OutboundMessageStatus.CANCELLED.value
    assert persisted.text_body is None
    email_service.send_transactional_email.assert_not_called()


@pytest.mark.asyncio
async def test_settlement_failure_after_sending_does_not_requeue_the_message(
    service, repository, seed_session, email_service, monkeypatch
):
    """The sent row must keep its spent attempt instead of being released and re-sent."""

    message = await _seed(seed_session)
    message_id = message.id

    async def broken_mark_delivered(*_args, **_kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(repository, "mark_delivered", broken_mark_delivered)

    with pytest.raises(RuntimeError):
        await service.run_once()

    persisted = await _reload(seed_session, message_id)
    assert persisted.status == OutboundMessageStatus.PROCESSING.value
    assert persisted.attempt_count == 1

    # The next cycle cannot pick it up: only the stale sweep can, after the lock timeout.
    email_service.send_transactional_email.reset_mock()
    assert await service.run_once() == 0
    email_service.send_transactional_email.assert_not_called()
