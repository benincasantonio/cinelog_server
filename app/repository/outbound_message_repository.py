"""PostgreSQL outbound-message (transactional outbox) repository implementation."""

from __future__ import annotations

from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbound_message_model import OutboundMessage
from app.repository.outbound_message_repository_protocol import (
    ClaimedMessage,
    StaleLockRecoveryResult,
)
from app.repository.repository_base import RepositoryBase
from app.schemas.outbound_message_schemas import OutboundMessageCreateData
from app.types import OutboundMessageChannel, OutboundMessageStatus

_STALE_LOCK_EXHAUSTED_ERROR = "Delivery lock expired after exhausting all retry attempts."


class OutboundMessageRepository(RepositoryBase):
    """Durable transactional-outbox persistence: enqueue, claim, and settle delivery."""

    async def enqueue(
        self,
        data: OutboundMessageCreateData,
        *,
        session: AsyncSession | None = None,
    ) -> UUID | None:
        """Insert a pending message once per ``(notification_id, channel)``.

        Uses the total unique constraint on ``(notification_id, channel)`` so retried or
        duplicate enqueue attempts are a database-level no-op — PostgreSQL treats NULL
        ``notification_id`` values as distinct, so auth-kind messages (which never
        reference a notification) never collide with each other and may repeat freely.
        """

        async with self._unit_of_work(session) as active_session:
            statement = (
                insert(OutboundMessage)
                .values(
                    kind=data.kind.value,
                    notification_id=data.notification_id,
                    channel=data.channel.value,
                    destination=data.destination,
                    subject=data.subject,
                    text_body=data.text_body,
                    html_body=data.html_body,
                )
                .on_conflict_do_nothing(constraint="uq_outbound_messages_notification_channel")
                .returning(OutboundMessage.id)
            )
            result = await active_session.execute(statement)
            return result.scalar_one_or_none()

    async def claim_pending_messages(
        self,
        channel: OutboundMessageChannel,
        *,
        batch_size: int,
    ) -> list[ClaimedMessage]:
        """Lock and claim up to ``batch_size`` due pending messages for one channel.

        Row locks acquired by ``FOR UPDATE SKIP LOCKED`` are held until commit, so a
        concurrent worker's claim query passes over rows this call already holds. Attempt
        count increments at claim time — before delivery is attempted — so a worker crash
        mid-send still burns an attempt and a poison message cannot loop forever.
        """

        async with self._session_provider() as session:
            candidates_statement = (
                select(OutboundMessage.id)
                .where(
                    OutboundMessage.channel == channel.value,
                    OutboundMessage.status == OutboundMessageStatus.PENDING.value,
                    OutboundMessage.available_at <= func.now(),
                    OutboundMessage.active(),
                )
                .order_by(OutboundMessage.available_at, OutboundMessage.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            candidate_ids = (await session.execute(candidates_statement)).scalars().all()
            if not candidate_ids:
                await session.commit()
                return []

            claimed_statement = (
                update(OutboundMessage)
                .where(OutboundMessage.id.in_(candidate_ids))
                .values(
                    status=OutboundMessageStatus.PROCESSING.value,
                    locked_at=func.now(),
                    attempt_count=OutboundMessage.attempt_count + 1,
                )
                .returning(
                    OutboundMessage.id,
                    OutboundMessage.kind,
                    OutboundMessage.channel,
                    OutboundMessage.destination,
                    OutboundMessage.subject,
                    OutboundMessage.text_body,
                    OutboundMessage.html_body,
                    OutboundMessage.attempt_count,
                )
            )
            rows = (await session.execute(claimed_statement)).all()
            await session.commit()
            return [
                ClaimedMessage(
                    id=row.id,
                    kind=row.kind,
                    channel=row.channel,
                    destination=row.destination,
                    subject=row.subject,
                    text_body=row.text_body,
                    html_body=row.html_body,
                    attempt_count=row.attempt_count,
                )
                for row in rows
            ]

    async def mark_delivered(self, message_id: UUID) -> None:
        """Record a successful delivery and clear rendered content.

        No ``status == processing`` guard: if a stale-lock sweep already requeued this
        row concurrently, the message was still sent, and recording delivery here is what
        prevents a duplicate send on the next claim.
        """

        async with self._session_provider() as session:
            await session.execute(
                update(OutboundMessage)
                .where(OutboundMessage.id == message_id)
                .values(
                    status=OutboundMessageStatus.DELIVERED.value,
                    delivered_at=func.now(),
                    locked_at=None,
                    last_error=None,
                    text_body=None,
                    html_body=None,
                )
            )
            await session.commit()

    async def schedule_retry(
        self,
        message_id: UUID,
        *,
        delay: timedelta,
        failure_detail: str,
    ) -> None:
        """Requeue a message for a future attempt, retaining its rendered content.

        ``delay`` is bound as a PostgreSQL INTERVAL so the retry clock is owned by the
        database rather than the worker's local clock.
        """

        async with self._session_provider() as session:
            await session.execute(
                update(OutboundMessage)
                .where(OutboundMessage.id == message_id)
                .values(
                    status=OutboundMessageStatus.PENDING.value,
                    available_at=func.now() + delay,
                    locked_at=None,
                    last_error=failure_detail,
                )
            )
            await session.commit()

    async def mark_failed(self, message_id: UUID, *, failure_detail: str) -> None:
        """Terminally fail a message and clear its rendered content."""

        async with self._session_provider() as session:
            await session.execute(
                update(OutboundMessage)
                .where(OutboundMessage.id == message_id)
                .values(
                    status=OutboundMessageStatus.FAILED.value,
                    locked_at=None,
                    last_error=failure_detail,
                    text_body=None,
                    html_body=None,
                )
            )
            await session.commit()

    async def recover_stale_locks(
        self,
        *,
        lock_timeout: timedelta,
        max_attempts: int,
    ) -> StaleLockRecoveryResult:
        """Requeue or terminally fail ``processing`` rows whose lock has expired.

        Runs in one transaction: rows that have exhausted ``max_attempts`` are marked
        ``failed`` first, then the remaining stale rows are requeued to ``pending``. The
        two updates share the same stale-lock predicate but disjoint attempt-count
        ranges, so a row can only match one of them.
        """

        async with self._session_provider() as session:
            stale_where = and_(
                OutboundMessage.status == OutboundMessageStatus.PROCESSING.value,
                OutboundMessage.active(),
                OutboundMessage.locked_at < func.now() - lock_timeout,
            )
            failed_result = await session.execute(
                update(OutboundMessage)
                .where(stale_where, OutboundMessage.attempt_count >= max_attempts)
                .values(
                    status=OutboundMessageStatus.FAILED.value,
                    locked_at=None,
                    last_error=_STALE_LOCK_EXHAUSTED_ERROR,
                    text_body=None,
                    html_body=None,
                )
                .execution_options(synchronize_session=False)
            )
            requeued_result = await session.execute(
                update(OutboundMessage)
                .where(stale_where, OutboundMessage.attempt_count < max_attempts)
                .values(
                    status=OutboundMessageStatus.PENDING.value,
                    available_at=func.now(),
                    locked_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            return StaleLockRecoveryResult(
                requeued=cast("CursorResult[tuple[object, ...]]", requeued_result).rowcount,
                failed=cast("CursorResult[tuple[object, ...]]", failed_result).rowcount,
            )
