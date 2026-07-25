"""Protocol and result types for outbound-message (transactional outbox) persistence."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.outbound_message_schemas import OutboundMessageCreateData
from app.types import OutboundMessageChannel, OutboundMessageKind


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

    async def mark_delivered(self, message_id: UUID, *, claimed_attempt: int) -> bool:
        """Record a successful delivery and clear rendered content.

        ``claimed_attempt`` fences the update to the attempt that claimed the row;
        returns ``False`` when that lease was lost to a newer attempt.
        """

    async def schedule_retry(
        self,
        message_id: UUID,
        *,
        claimed_attempt: int,
        delay: timedelta,
        failure_detail: str,
    ) -> bool:
        """Requeue a message for a future attempt, retaining its rendered content."""

    async def mark_failed(self, message_id: UUID, *, claimed_attempt: int, failure_detail: str) -> bool:
        """Terminally fail a message and clear its rendered content."""

    async def release_claims(self, leases: Sequence[tuple[UUID, int]]) -> int:
        """Return unprocessed claims to the queue and refund their attempt."""

    async def fail_expired_messages(self) -> int:
        """Terminally fail pending messages whose content has expired."""

    async def supersede_pending_messages(
        self,
        kind: OutboundMessageKind,
        destination: str,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        """Retire earlier undelivered messages of one kind for one destination."""

    async def recover_stale_locks(
        self,
        *,
        lock_timeout: timedelta,
        max_attempts: int,
    ) -> StaleLockRecoveryResult:
        """Requeue or terminally fail ``processing`` rows whose lock has expired."""
