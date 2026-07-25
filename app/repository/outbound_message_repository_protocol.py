"""Protocol and result types for outbound-message (transactional outbox) persistence."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
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
    # Fencing token for this claim; every settlement must present it.
    lock_token: UUID
    # Deadline for code-bearing content, rechecked immediately before sending.
    expires_at: datetime | None


class LeaseRenewal(StrEnum):
    """Outcome of refreshing a claim's lock immediately before sending."""

    RENEWED = "renewed"
    EXPIRED = "expired"
    LOST = "lost"


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

    async def renew_lease(self, message_id: UUID, *, lock_token: UUID) -> LeaseRenewal:
        """Refresh the lock before sending; retire the row when its content has expired."""

    async def mark_delivered(self, message_id: UUID, *, lock_token: UUID) -> bool:
        """Record a successful delivery and clear rendered content.

        ``lock_token`` fences the update to the claim that owns the row; returns
        ``False`` when that lease was lost to a newer claim.
        """

    async def schedule_retry(
        self,
        message_id: UUID,
        *,
        lock_token: UUID,
        delay: timedelta,
        failure_detail: str,
    ) -> bool:
        """Requeue a message for a future attempt, retaining its rendered content."""

    async def mark_failed(self, message_id: UUID, *, lock_token: UUID, failure_detail: str) -> bool:
        """Terminally fail a message and clear its rendered content."""

    async def release_claims(self, leases: Sequence[tuple[UUID, UUID]]) -> int:
        """Return unprocessed claims to the queue and refund their attempt.

        Takes ``(message_id, lock_token)`` pairs and is fenced on the token.
        """

    async def cancel_expired_messages(self) -> int:
        """Terminally fail pending messages whose content has expired."""

    async def enqueue_superseding(
        self,
        data: OutboundMessageCreateData,
        *,
        session: AsyncSession | None = None,
    ) -> UUID | None:
        """Supersede still-queued messages for this kind/destination and insert, atomically."""

    async def supersede_pending_messages(
        self,
        kind: OutboundMessageKind,
        destination: str,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        """Retire earlier undelivered messages of one kind for one destination."""

    async def purge_settled_messages(
        self,
        *,
        delivered_retention: timedelta,
        failed_retention: timedelta,
        batch_size: int = 1000,
    ) -> int:
        """Delete a bounded batch of settled rows past their retention window."""

    async def recover_stale_locks(
        self,
        *,
        lock_timeout: timedelta,
        max_attempts: int,
    ) -> StaleLockRecoveryResult:
        """Requeue or terminally fail ``processing`` rows whose lock has expired."""
