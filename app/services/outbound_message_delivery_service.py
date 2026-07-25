"""Outbound-message delivery: one claim-and-send cycle.

Owns a single delivery cycle with no loop and no signal handling — those are process
concerns that belong to ``app/workers/outbound_message_worker.py``. Keeping the cycle
here, free of ``asyncio.run``/signal handling, makes it directly unit-testable.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta

from app.config.outbound_message_config import (
    OutboundMessageWorkerConfig,
    compute_retry_delay,
    get_outbound_message_worker_config,
)
from app.repository.outbound_message_repository_protocol import (
    ClaimedMessage,
    OutboundMessageRepositoryProtocol,
    StaleLockRecoveryResult,
)
from app.services.email_service import EmailService
from app.types import OutboundMessageChannel
from app.utils.sanitize_utils import sanitize_failure_detail


class OutboundMessageDeliveryService:
    """Recover stale locks, claim due messages, and deliver each one."""

    def __init__(
        self,
        outbound_message_repository: OutboundMessageRepositoryProtocol,
        email_service: EmailService | None = None,
        worker_config: OutboundMessageWorkerConfig | None = None,
    ) -> None:
        self.outbound_message_repository = outbound_message_repository
        self.email_service = email_service or EmailService()
        self.worker_config = worker_config or get_outbound_message_worker_config()
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
        """Recover stale locks, claim one batch, and deliver each claimed message.

        Returns the number of messages processed (delivered or failed/retried), so
        the caller's poll loop can decide whether to sleep. Stops between rows when
        ``shutdown`` is set — a message already claimed but not yet delivered is
        picked up again by the next stale-lock sweep.
        """

        await self.recover_stale_locks()
        claimed = await self.outbound_message_repository.claim_pending_messages(
            OutboundMessageChannel.EMAIL,
            batch_size=self.worker_config.batch_size,
        )

        processed = 0
        for message in claimed:
            if shutdown is not None and shutdown.is_set():
                break
            await self._deliver(message)
            processed += 1
        return processed

    async def _deliver(self, message: ClaimedMessage) -> None:
        sender = self._channel_senders.get(message.channel)
        if sender is None:
            await self._record_failure(message, ValueError(f"No delivery handler for channel {message.channel!r}"))
            return

        try:
            await sender(message)
        except Exception as error:  # any transport failure must be recorded, never propagated
            await self._record_failure(message, error)
            return

        await self.outbound_message_repository.mark_delivered(message.id)

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
            await self.outbound_message_repository.mark_failed(message.id, failure_detail=failure_detail)
            return

        delay_seconds = compute_retry_delay(message.attempt_count, self.worker_config)
        await self.outbound_message_repository.schedule_retry(
            message.id,
            delay=timedelta(seconds=delay_seconds),
            failure_detail=failure_detail,
        )
