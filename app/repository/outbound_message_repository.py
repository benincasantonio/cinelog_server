"""PostgreSQL outbound-message (transactional outbox) repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, and_, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbound_message_model import OutboundMessage
from app.repository.outbound_message_repository_protocol import (
    ClaimedMessage,
    StaleLockRecoveryResult,
)
from app.repository.repository_base import RepositoryBase
from app.schemas.outbound_message_schemas import OutboundMessageCreateData
from app.types import OutboundMessageChannel, OutboundMessageKind, OutboundMessageStatus

_STALE_LOCK_EXHAUSTED_ERROR = "Delivery lock expired after exhausting all retry attempts."
_EXPIRED_ERROR = "Message content expired before delivery."
_SUPERSEDED_ERROR = "Superseded by a newer message for the same recipient."


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
                    expires_at=data.expires_at,
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
                    # An expired code must never be claimed; ``fail_expired_messages``
                    # retires these rows and clears their rendered content.
                    or_(
                        OutboundMessage.expires_at.is_(None),
                        OutboundMessage.expires_at > func.now(),
                    ),
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
                    # PostgreSQL mints the token so every row in the batch gets its own
                    # value; a Python-side UUID would be shared across the whole UPDATE.
                    lock_token=func.gen_random_uuid(),
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
                    OutboundMessage.lock_token,
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
                    lock_token=row.lock_token,
                )
                for row in rows
            ]

    def _lease_predicate(self, message_id: UUID, lock_token: UUID):
        """Restrict a settlement to the exact claim that owns the row.

        ``FOR UPDATE SKIP LOCKED`` stops two workers claiming the same row at the same
        moment, but it says nothing once the transaction commits: a worker that hangs
        long enough for its lock to be declared stale wakes up believing it still owns a
        row another attempt has since claimed. The per-claim ``lock_token`` closes that
        window — it is minted fresh on every claim and cleared whenever a lock ends, so a
        superseded worker matches zero rows.

        Without it, a slow attempt reporting failure could regress a row that a newer
        attempt had already delivered and emptied, leaving a pending message with no
        rendered content for any later attempt to send.
        """

        return and_(
            OutboundMessage.id == message_id,
            OutboundMessage.status == OutboundMessageStatus.PROCESSING.value,
            OutboundMessage.lock_token == lock_token,
        )

    async def mark_delivered(self, message_id: UUID, *, lock_token: UUID) -> bool:
        """Record a successful delivery and clear rendered content.

        Returns ``False`` when the lease was lost — the row had already been recovered
        and re-claimed, so the newer attempt owns the outcome. The message was still
        sent, which is the duplicate that at-least-once delivery accepts.
        """

        async with self._session_provider() as session:
            result = await session.execute(
                update(OutboundMessage)
                .where(self._lease_predicate(message_id, lock_token))
                .values(
                    status=OutboundMessageStatus.DELIVERED.value,
                    delivered_at=func.now(),
                    locked_at=None,
                    lock_token=None,
                    last_error=None,
                    text_body=None,
                    html_body=None,
                )
            )
            await session.commit()
            return cast("CursorResult[tuple[object, ...]]", result).rowcount > 0

    async def schedule_retry(
        self,
        message_id: UUID,
        *,
        lock_token: UUID,
        delay: timedelta,
        failure_detail: str,
    ) -> bool:
        """Requeue a message for a future attempt, retaining its rendered content.

        ``delay`` is bound as a PostgreSQL INTERVAL so the retry clock is owned by the
        database rather than the worker's local clock. Returns ``False`` when the lease
        was lost, leaving the newer attempt's state untouched.
        """

        async with self._session_provider() as session:
            result = await session.execute(
                update(OutboundMessage)
                .where(self._lease_predicate(message_id, lock_token))
                .values(
                    status=OutboundMessageStatus.PENDING.value,
                    available_at=func.now() + delay,
                    locked_at=None,
                    lock_token=None,
                    last_error=failure_detail,
                )
            )
            await session.commit()
            return cast("CursorResult[tuple[object, ...]]", result).rowcount > 0

    async def mark_failed(self, message_id: UUID, *, lock_token: UUID, failure_detail: str) -> bool:
        """Terminally fail a message and clear its rendered content.

        Returns ``False`` when the lease was lost.
        """

        async with self._session_provider() as session:
            result = await session.execute(
                update(OutboundMessage)
                .where(self._lease_predicate(message_id, lock_token))
                .values(
                    status=OutboundMessageStatus.FAILED.value,
                    locked_at=None,
                    lock_token=None,
                    last_error=failure_detail,
                    text_body=None,
                    html_body=None,
                )
            )
            await session.commit()
            return cast("CursorResult[tuple[object, ...]]", result).rowcount > 0

    async def release_claims(self, leases: Sequence[tuple[UUID, UUID]]) -> int:
        """Return unprocessed claims to the queue and refund their attempt.

        A batch claim locks every row and burns an attempt up front, so rows the worker
        never reached — because it is shutting down, or the cycle failed — would
        otherwise sit locked until the stale sweep and lose an attempt they never spent.
        Takes ``(message_id, lock_token)`` pairs and is fenced on the token, so a row
        whose lock was recovered and re-claimed elsewhere is left to its new owner.
        """

        if not leases:
            return 0

        async with self._session_provider() as session:
            result = await session.execute(
                update(OutboundMessage)
                .where(
                    tuple_(OutboundMessage.id, OutboundMessage.lock_token).in_(leases),
                    OutboundMessage.status == OutboundMessageStatus.PROCESSING.value,
                )
                .values(
                    status=OutboundMessageStatus.PENDING.value,
                    locked_at=None,
                    lock_token=None,
                    available_at=func.now(),
                    attempt_count=OutboundMessage.attempt_count - 1,
                )
            )
            await session.commit()
            return cast("CursorResult[tuple[object, ...]]", result).rowcount

    async def fail_expired_messages(self) -> int:
        """Terminally fail pending messages whose content has expired.

        Retires the row rather than delivering a code the recipient can no longer use,
        and clears the rendered body so an expired secret stops sitting in the table.
        """

        async with self._session_provider() as session:
            result = await session.execute(
                update(OutboundMessage)
                .where(
                    OutboundMessage.status == OutboundMessageStatus.PENDING.value,
                    OutboundMessage.active(),
                    OutboundMessage.expires_at.is_not(None),
                    OutboundMessage.expires_at <= func.now(),
                )
                .values(
                    status=OutboundMessageStatus.FAILED.value,
                    locked_at=None,
                    lock_token=None,
                    last_error=_EXPIRED_ERROR,
                    text_body=None,
                    html_body=None,
                )
            )
            await session.commit()
            return cast("CursorResult[tuple[object, ...]]", result).rowcount

    async def supersede_pending_messages(
        self,
        kind: OutboundMessageKind,
        destination: str,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        """Retire earlier undelivered messages of one kind for one destination.

        Reissuing a code invalidates the previous one, so any still-queued message
        carrying it must not be delivered. Only ``pending`` rows are touched: a row
        currently being processed is owned by its lease holder and settles normally.
        """

        async with self._unit_of_work(session) as active_session:
            result = await active_session.execute(
                update(OutboundMessage)
                .where(
                    OutboundMessage.kind == kind.value,
                    OutboundMessage.destination == destination,
                    OutboundMessage.status == OutboundMessageStatus.PENDING.value,
                    OutboundMessage.active(),
                )
                .values(
                    status=OutboundMessageStatus.FAILED.value,
                    locked_at=None,
                    lock_token=None,
                    last_error=_SUPERSEDED_ERROR,
                    text_body=None,
                    html_body=None,
                )
            )
            return cast("CursorResult[tuple[object, ...]]", result).rowcount

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
                    lock_token=None,
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
                    lock_token=None,
                )
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            return StaleLockRecoveryResult(
                requeued=cast("CursorResult[tuple[object, ...]]", requeued_result).rowcount,
                failed=cast("CursorResult[tuple[object, ...]]", failed_result).rowcount,
            )
