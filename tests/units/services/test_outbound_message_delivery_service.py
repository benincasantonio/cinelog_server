"""Unit tests for one outbound-message delivery cycle."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config.outbound_message_config import OutboundMessageWorkerConfig
from app.repository.outbound_message_repository_protocol import (
    ClaimedMessage,
    LeaseRenewal,
    StaleLockRecoveryResult,
)
from app.services.outbound_message_delivery_service import OutboundMessageDeliveryService
from app.types import OutboundMessageChannel, OutboundMessageKind


def _worker_config(**overrides) -> OutboundMessageWorkerConfig:
    defaults = {
        "batch_size": 10,
        "poll_interval": 5,
        "lock_timeout": 300,
        "max_retries": 4,
        "retry_base_delay": 60,
        "retry_max_delay": 3600,
        "delivered_retention_days": 30,
        "failed_retention_days": 90,
        "purge_interval": 0,
        "purge_batch_size": 1000,
        "retry_jitter_ratio": 0.0,
    }
    defaults.update(overrides)
    return OutboundMessageWorkerConfig(**defaults)


def _claimed_message(**overrides) -> ClaimedMessage:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "kind": OutboundMessageKind.REGISTRATION_VERIFICATION.value,
        "channel": OutboundMessageChannel.EMAIL.value,
        "destination": "user@example.com",
        "subject": "Subject",
        "text_body": "text",
        "html_body": "<p>html</p>",
        "attempt_count": 1,
        "lock_token": uuid4(),
        "expires_at": None,
    }
    defaults.update(overrides)
    return ClaimedMessage(**defaults)


@pytest.fixture
def repository():
    mock_repository = AsyncMock()
    mock_repository.recover_stale_locks.return_value = StaleLockRecoveryResult(requeued=0, failed=0)
    mock_repository.claim_pending_messages.return_value = []
    mock_repository.renew_lease.return_value = LeaseRenewal.RENEWED
    return mock_repository


@pytest.fixture
def email_service():
    return MagicMock()


@pytest.fixture
def service(repository, email_service):
    return OutboundMessageDeliveryService(
        outbound_message_repository=repository,
        email_service=email_service,
        worker_config=_worker_config(),
    )


@pytest.mark.asyncio
async def test_run_once_recovers_stale_locks_every_cycle(service, repository):
    await service.run_once()

    repository.recover_stale_locks.assert_awaited_once_with(lock_timeout=timedelta(seconds=300), max_attempts=5)


@pytest.mark.asyncio
async def test_recover_stale_locks_delegates_to_repository(service, repository):
    repository.recover_stale_locks.return_value = StaleLockRecoveryResult(requeued=2, failed=1)

    result = await service.recover_stale_locks()

    assert result == StaleLockRecoveryResult(requeued=2, failed=1)
    repository.recover_stale_locks.assert_awaited_once_with(lock_timeout=timedelta(seconds=300), max_attempts=5)


@pytest.mark.asyncio
async def test_run_once_returns_zero_when_nothing_is_claimed(service):
    assert await service.run_once() == 0


@pytest.mark.asyncio
async def test_run_once_delivers_a_successful_message(service, repository, email_service):
    message = _claimed_message()
    repository.claim_pending_messages.return_value = [message]

    processed = await service.run_once()

    assert processed == 1
    email_service.send_transactional_email.assert_called_once_with(
        to_email=message.destination,
        subject=message.subject,
        text=message.text_body,
        html=message.html_body,
    )
    repository.mark_delivered.assert_awaited_once_with(message.id, lock_token=message.lock_token)


@pytest.mark.asyncio
async def test_send_runs_off_the_event_loop(service, repository, email_service):
    message = _claimed_message()
    repository.claim_pending_messages.return_value = [message]

    with patch("app.services.outbound_message_delivery_service.asyncio.to_thread", new=AsyncMock()) as to_thread:
        await service.run_once()

    to_thread.assert_awaited_once_with(
        email_service.send_transactional_email,
        to_email=message.destination,
        subject=message.subject,
        text=message.text_body,
        html=message.html_body,
    )


@pytest.mark.asyncio
async def test_retryable_failure_schedules_retry_with_exact_backoff(service, repository, email_service):
    message = _claimed_message(attempt_count=2)
    repository.claim_pending_messages.return_value = [message]
    email_service.send_transactional_email.side_effect = RuntimeError("smtp exploded")

    await service.run_once()

    repository.mark_failed.assert_not_awaited()
    repository.schedule_retry.assert_awaited_once()
    _, kwargs = repository.schedule_retry.await_args
    assert kwargs["delay"] == timedelta(seconds=120)
    assert kwargs["failure_detail"] == "smtp exploded"
    assert kwargs["lock_token"] == message.lock_token


@pytest.mark.asyncio
async def test_exhausted_attempts_marks_failed_instead_of_retrying(service, repository, email_service):
    message = _claimed_message(attempt_count=5)
    repository.claim_pending_messages.return_value = [message]
    email_service.send_transactional_email.side_effect = RuntimeError("smtp exploded")

    await service.run_once()

    repository.schedule_retry.assert_not_awaited()
    repository.mark_failed.assert_awaited_once_with(
        message.id, lock_token=message.lock_token, failure_detail="smtp exploded"
    )


@pytest.mark.asyncio
async def test_failure_detail_is_sanitized_and_truncated(service, repository, email_service):
    message = _claimed_message(attempt_count=5)
    repository.claim_pending_messages.return_value = [message]
    email_service.send_transactional_email.side_effect = RuntimeError(
        "failed for user@example.com password=hunter2 " + "x" * 600
    )

    await service.run_once()

    _, kwargs = repository.mark_failed.await_args
    detail = kwargs["failure_detail"]
    assert "user@example.com" not in detail
    assert "hunter2" not in detail
    assert len(detail) <= 500


@pytest.mark.asyncio
async def test_deliver_records_failure_when_claimed_message_is_missing_rendered_content(
    service, repository, email_service
):
    message = _claimed_message(text_body=None, html_body=None, attempt_count=1)
    repository.claim_pending_messages.return_value = [message]

    await service.run_once()

    email_service.send_transactional_email.assert_not_called()
    repository.schedule_retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_once_stops_between_rows_when_shutdown_is_set(service, repository, email_service):
    first = _claimed_message(destination="first@example.com")
    second = _claimed_message(destination="second@example.com")
    repository.claim_pending_messages.return_value = [first, second]
    shutdown = asyncio.Event()
    email_service.send_transactional_email.side_effect = lambda **kwargs: shutdown.set()

    processed = await service.run_once(shutdown)

    assert processed == 1
    repository.mark_delivered.assert_awaited_once_with(first.id, lock_token=first.lock_token)
    # The row the worker never reached goes back to the queue with its attempt
    # refunded, rather than sitting locked until the stale sweep.
    repository.release_claims.assert_awaited_once_with([(second.id, second.lock_token)])


@pytest.mark.asyncio
async def test_run_once_retires_expired_messages_before_claiming(service, repository):
    repository.cancel_expired_messages.return_value = 2

    await service.run_once()

    repository.cancel_expired_messages.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_message_whose_settlement_fails_after_sending_is_never_released(service, repository, email_service):
    """SMTP ran; the row must keep its spent attempt rather than be requeued.

    Releasing it would refund the attempt, so a settlement error that recurs for that
    row would re-send the same email every cycle, unbounded by max_attempts.
    """

    first = _claimed_message(destination="first@example.com")
    second = _claimed_message(destination="second@example.com")
    repository.claim_pending_messages.return_value = [first, second]
    repository.mark_delivered.side_effect = RuntimeError("database went away")

    with pytest.raises(RuntimeError):
        await service.run_once()

    email_service.send_transactional_email.assert_called_once()
    # Only the message never handed to _deliver goes back to the queue.
    repository.release_claims.assert_awaited_once_with([(second.id, second.lock_token)])


@pytest.mark.asyncio
async def test_shutdown_before_the_first_delivery_releases_the_whole_batch(service, repository, email_service):
    """A SIGTERM landing between claim and first send must not strand the batch."""

    first = _claimed_message(destination="first@example.com")
    second = _claimed_message(destination="second@example.com")
    repository.claim_pending_messages.return_value = [first, second]
    shutdown = asyncio.Event()
    shutdown.set()

    processed = await service.run_once(shutdown)

    assert processed == 0
    email_service.send_transactional_email.assert_not_called()
    repository.release_claims.assert_awaited_once_with([(first.id, first.lock_token), (second.id, second.lock_token)])


@pytest.mark.asyncio
async def test_expired_message_is_retired_without_sending(service, repository, email_service):
    message = _claimed_message(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    repository.claim_pending_messages.return_value = [message]
    repository.renew_lease.return_value = LeaseRenewal.EXPIRED

    processed = await service.run_once()

    assert processed == 1
    email_service.send_transactional_email.assert_not_called()
    repository.mark_delivered.assert_not_awaited()
    repository.schedule_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_lost_lease_before_sending_skips_the_send(service, repository, email_service):
    message = _claimed_message()
    repository.claim_pending_messages.return_value = [message]
    repository.renew_lease.return_value = LeaseRenewal.LOST

    await service.run_once()

    email_service.send_transactional_email.assert_not_called()
    repository.mark_delivered.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_once_purges_settled_messages_with_configured_retention(service, repository):
    repository.purge_settled_messages.return_value = 3

    await service.run_once()

    repository.purge_settled_messages.assert_awaited_once_with(
        delivered_retention=timedelta(days=30),
        failed_retention=timedelta(days=90),
        batch_size=1000,
    )


@pytest.mark.asyncio
async def test_lost_lease_on_success_is_logged_and_not_retried(service, repository, caplog):
    message = _claimed_message()
    repository.claim_pending_messages.return_value = [message]
    repository.mark_delivered.return_value = False

    with caplog.at_level("WARNING"):
        processed = await service.run_once()

    assert processed == 1
    repository.schedule_retry.assert_not_awaited()
    repository.mark_failed.assert_not_awaited()
    assert "lease" in caplog.text
