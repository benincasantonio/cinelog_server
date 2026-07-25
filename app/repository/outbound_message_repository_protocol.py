"""Protocol and result types for outbound-message (transactional outbox) persistence."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.outbound_message_schemas import OutboundMessageCreateData
from app.types import OutboundMessageChannel


@dataclass(frozen=True)
class ClaimedMessage:
    """One outbound message claimed for delivery by this worker."""

    id: UUID
    kind: str
    channel: str
    destination: str
    subject: str
    text_body: str | None
    html_body: str | None
    attempt_count: int


@dataclass(frozen=True)
class StaleLockRecoveryResult:
    """Outcome of sweeping ``processing`` rows whose lock has expired."""

    requeued: int
    failed: int


class OutboundMessageRepositoryProtocol(Protocol):
    """Outbound-message repository operations used by the enqueue and delivery services."""

    async def enqueue(
        self,
        data: OutboundMessageCreateData,
        *,
        session: AsyncSession | None = None,
    ) -> UUID | None:
        """Insert a pending message once per ``(notification_id, channel)``.

        Returns ``None`` when a message for that pair already exists. Accepts an
        optional ``session`` so a unit of work can join an existing transaction.
        """

    async def claim_pending_messages(
        self,
        channel: OutboundMessageChannel,
        *,
        batch_size: int,
    ) -> list[ClaimedMessage]:
        """Lock and claim up to ``batch_size`` due pending messages for one channel."""

    async def mark_delivered(self, message_id: UUID) -> None:
        """Record a successful delivery and clear rendered content."""

    async def schedule_retry(
        self,
        message_id: UUID,
        *,
        delay: timedelta,
        failure_detail: str,
    ) -> None:
        """Requeue a message for a future attempt, retaining its rendered content."""

    async def mark_failed(self, message_id: UUID, *, failure_detail: str) -> None:
        """Terminally fail a message and clear its rendered content."""

    async def recover_stale_locks(
        self,
        *,
        lock_timeout: timedelta,
        max_attempts: int,
    ) -> StaleLockRecoveryResult:
        """Requeue or terminally fail ``processing`` rows whose lock has expired."""
