"""Outbound-message delivery: one claim-and-send cycle.

Owns a single delivery cycle with no loop and no signal handling — those are process
concerns that belong to ``app/workers/outbound_message_worker.py``. Keeping the cycle
here, free of ``asyncio.run``/signal handling, makes it directly unit-testable.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import timedelta

from app.config.outbound_message_config import OutboundMessageWorkerConfig, compute_retry_delay
from app.repository.outbound_message_repository_protocol import (
    ClaimedMessage,
    LeaseRenewal,
    OutboundMessageRepositoryProtocol,
    StaleLockRecoveryResult,
)
from app.services.email_service import EmailService
from app.types import OutboundMessageChannel
from app.utils.sanitize_utils import sanitize_failure_detail

logger = logging.getLogger(__name__)


class OutboundMessageDeliveryService:
    """Recover stale locks, claim due messages, and deliver each one."""

    def __init__(
        self,
        outbound_message_repository: OutboundMessageRepositoryProtocol,
        email_service: EmailService,
        worker_config: OutboundMessageWorkerConfig,
    ) -> None:
        self.outbound_message_repository = outbound_message_repository
        self.email_service = email_service
        self.worker_config = worker_config
        self._channel_senders: dict[str, Callable[[ClaimedMessage], Awaitable[None]]] = {
            OutboundMessageChannel.EMAIL.value: self._send_email,
        }

    async def recover_stale_locks(self) -> StaleLockRecoveryResult:
        """Requeue or terminally fail ``processing`` rows whose lock has expired."""

        return await self.outbound_message_repository.recover_stale_locks(
            lock_timeout=timedelta(seconds=self.worker_config.lock_timeout),
            max_attempts=self.worker_config.max_attempts,
        )

    async def run_once(self, shutdown: asyncio.Event | None = None) -> int:
        """Retire expired rows, recover stale locks, claim one batch, and deliver it.

        Returns the number of messages processed (delivered or failed/retried), so the
        caller's poll loop can decide whether to sleep. A claim locks the whole batch and
        spends an attempt on every row up front, so anything left unprocessed — because
        the worker is shutting down, or the cycle raised — is released back to the queue
        with its attempt refunded rather than left locked until the stale sweep.
        """

        await self.cancel_expired_messages()
        await self.purge_settled_messages()
        await self.recover_stale_locks()
        claimed = await self.outbound_message_repository.claim_pending_messages(
            OutboundMessageChannel.EMAIL,
            batch_size=self.worker_config.batch_size,
        )

        processed = 0
        started = 0
        try:
            for message in claimed:
                if shutdown is not None and shutdown.is_set():
                    break
                # Count the message as started *before* delivery. Once SMTP may have
                # run, the row must never be released: releasing refunds the attempt, so
                # a settlement that failed after a successful send would be re-claimed
                # and re-sent every cycle, unbounded by max_attempts.
                started += 1
                await self._deliver(message)
                processed += 1
        finally:
            await self._release_unprocessed(claimed[started:])
        return processed

    async def cancel_expired_messages(self) -> int:
        """Retire pending messages whose content expired before it could be sent."""

        retired = await self.outbound_message_repository.cancel_expired_messages()
        if retired:
            logger.info("Retired %d outbound message(s) whose content had expired", retired)
        return retired

    async def purge_settled_messages(self) -> int:
        """Delete settled rows past their retention window.

        Settled rows still hold a recipient address, so the outbox is pruned on a
        schedule rather than growing without bound.
        """

        purged = await self.outbound_message_repository.purge_settled_messages(
            delivered_retention=timedelta(days=self.worker_config.delivered_retention_days),
            failed_retention=timedelta(days=self.worker_config.failed_retention_days),
        )
        if purged:
            logger.info("Purged %d settled outbound message(s) past their retention window", purged)
        return purged

    async def _release_unprocessed(self, remaining: Sequence[ClaimedMessage]) -> None:
        if not remaining:
            return

        released = await self.outbound_message_repository.release_claims(
            [(message.id, message.lock_token) for message in remaining]
        )
        logger.info("Released %d unprocessed outbound message claim(s) back to the queue", released)

    async def _deliver(self, message: ClaimedMessage) -> None:
        sender = self._channel_senders.get(message.channel)
        if sender is None:
            await self._record_failure(message, ValueError(f"No delivery handler for channel {message.channel!r}"))
            return

        # Refresh the lease and re-evaluate expiry against the database clock at the
        # moment of sending: this message may have waited behind earlier sends in the
        # same serial batch, long enough for its code to expire or its lock to lapse.
        renewal = await self.outbound_message_repository.renew_lease(message.id, lock_token=message.lock_token)
        if renewal is LeaseRenewal.EXPIRED:
            logger.info("Message %s expired while queued; retired without sending", message.id)
            return
        if renewal is LeaseRenewal.LOST:
            logger.warning("Lease for message %s was lost before sending; another attempt owns it", message.id)
            return

        try:
            await sender(message)
        except Exception as error:  # any transport failure must be recorded, never propagated
            await self._record_failure(message, error)
            return

        settled = await self.outbound_message_repository.mark_delivered(
            message.id,
            lock_token=message.lock_token,
        )
        if not settled:
            logger.warning(
                "Delivered message %s but its lease had already been recovered; "
                "another attempt owns the outcome and may resend",
                message.id,
            )

    async def _send_email(self, message: ClaimedMessage) -> None:
        if message.text_body is None or message.html_body is None:
            raise ValueError(f"Claimed message {message.id} is missing rendered content")

        # smtplib is blocking; run it off the event loop rather than adding an
        # aiosmtplib dependency.
        await asyncio.to_thread(
            self.email_service.send_transactional_email,
            to_email=message.destination,
            subject=message.subject,
            text=message.text_body,
            html=message.html_body,
        )

    async def _record_failure(self, message: ClaimedMessage, error: Exception) -> None:
        failure_detail = sanitize_failure_detail(str(error))
        if message.attempt_count >= self.worker_config.max_attempts:
            settled = await self.outbound_message_repository.mark_failed(
                message.id,
                lock_token=message.lock_token,
                failure_detail=failure_detail,
            )
        else:
            delay_seconds = compute_retry_delay(message.attempt_count, self.worker_config)
            settled = await self.outbound_message_repository.schedule_retry(
                message.id,
                lock_token=message.lock_token,
                delay=timedelta(seconds=delay_seconds),
                failure_detail=failure_detail,
            )

        if not settled:
            logger.warning(
                "Failure for message %s was not recorded; its lease had already been recovered",
                message.id,
            )
