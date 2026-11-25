"""PostgreSQL notification repository implementation."""

from __future__ import annotations

from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.notification_config import FOLLOW_STARTED_NOTIFICATION_COOLDOWN_SECONDS
from app.models.notification_model import Notification
from app.repository.notification_repository_protocol import (
    MarkAllNotificationsReadResult,
    NotificationCreateResult,
    NotificationPage,
)
from app.repository.repository_base import RepositoryBase
from app.schemas.notification_schemas import NotificationCreateData
from app.types import NotificationType, TimestampUUIDCursor


class NotificationRepository(RepositoryBase):
    """Recipient-scoped notification persistence."""

    async def _find_by_id(
        self,
        session: AsyncSession,
        notification_id: UUID,
        recipient_id: UUID | None = None,
    ) -> Notification | None:
        statement = (
            select(Notification)
            .options(selectinload(Notification.actor))
            .where(Notification.id == notification_id, Notification.active())
        )
        if recipient_id is not None:
            statement = statement.where(Notification.recipient_id == recipient_id)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def create_notification(
        self, data: NotificationCreateData, *, session: AsyncSession | None = None
    ) -> NotificationCreateResult:
        """Create once per active event key; a supplied session owns the transaction."""

        if session is None:
            async with self._session_provider() as owned_session:
                async with owned_session.begin():
                    created_result = await self.create_notification(data, session=owned_session)
                return created_result

        # Timestamps come from PostgreSQL rather than the base entity's Python
        # default so seek pagination stays consistently ordered across API instances.
        statement = (
            insert(Notification)
            .values(
                recipient_id=data.recipient_id,
                actor_id=data.actor_id,
                type=data.type.value,
                title=data.title,
                body=data.body,
                deduplication_key=data.deduplication_key,
                created_at=func.now(),
                updated_at=func.now(),
            )
            .on_conflict_do_nothing(
                index_elements=[Notification.recipient_id, Notification.deduplication_key],
                index_where=and_(
                    Notification.deleted.is_(False),
                    Notification.deduplication_key.is_not(None),
                ),
            )
            .returning(Notification.id)
        )
        result = await session.execute(statement)
        inserted_id = result.scalar_one_or_none()
        created = inserted_id is not None

        if inserted_id is None:
            if data.deduplication_key is None:
                raise RuntimeError("Notification insert returned no row without a deduplication key")
            existing_result = await session.execute(
                select(Notification.id).where(
                    Notification.recipient_id == data.recipient_id,
                    Notification.deduplication_key == data.deduplication_key,
                    Notification.active(),
                )
            )
            inserted_id = existing_result.scalar_one()

        notification = await self._find_by_id(session, inserted_id)
        if notification is None:
            raise RuntimeError("Notification insert could not be reloaded")

        return NotificationCreateResult(notification=notification, created=created)

    async def has_recent_follow_started(self, recipient_id: UUID, actor_id: UUID, *, session: AsyncSession) -> bool:
        """Include read and deleted history so inbox changes cannot reset the cooldown."""
        statement = select(
            select(Notification.id)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.actor_id == actor_id,
                Notification.type == NotificationType.FOLLOW_STARTED.value,
                Notification.created_at > func.now() - timedelta(seconds=FOLLOW_STARTED_NOTIFICATION_COOLDOWN_SECONDS),
            )
            .exists()
        )
        return bool(await session.scalar(statement))

    async def list_notifications(
        self,
        recipient_id: UUID,
        *,
        unread_only: bool,
        limit: int,
        cursor: TimestampUUIDCursor | None,
    ) -> NotificationPage:
        """List active notifications newest first with stable seek pagination."""

        async with self._session_provider() as session:
            statement = (
                select(Notification)
                .options(selectinload(Notification.actor))
                .where(Notification.recipient_id == recipient_id, Notification.active())
            )
            if unread_only:
                statement = statement.where(Notification.read_at.is_(None))
            if cursor is not None:
                statement = statement.where(
                    or_(
                        Notification.created_at < cursor.timestamp,
                        and_(
                            Notification.created_at == cursor.timestamp,
                            Notification.id < cursor.id,
                        ),
                    )
                )

            result = await session.execute(
                statement.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
            )
            fetched = list(result.scalars().all())
            items = fetched[:limit]

            unread_result = await session.execute(
                select(func.count(Notification.id)).where(
                    Notification.recipient_id == recipient_id,
                    Notification.active(),
                    Notification.read_at.is_(None),
                )
            )
            return NotificationPage(
                items=items,
                has_more=len(fetched) > limit,
                unread_count=unread_result.scalar_one(),
            )

    async def mark_notification_read(
        self,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> Notification | None:
        """Set the database-owned read timestamp once for an owned active row."""

        async with self._session_provider() as session:
            await session.execute(
                update(Notification)
                .where(
                    Notification.id == notification_id,
                    Notification.recipient_id == recipient_id,
                    Notification.active(),
                    Notification.read_at.is_(None),
                )
                .values(read_at=func.now(), updated_at=func.now())
                .execution_options(synchronize_session=False)
            )
            notification = await self._find_by_id(session, notification_id, recipient_id)
            await session.commit()
            return notification

    async def mark_all_notifications_read(self, recipient_id: UUID) -> MarkAllNotificationsReadResult:
        """Mark active unread rows with one transaction timestamp and recount."""

        async with self._session_provider() as session:
            update_result = await session.execute(
                update(Notification)
                .where(
                    Notification.recipient_id == recipient_id,
                    Notification.active(),
                    Notification.read_at.is_(None),
                )
                .values(read_at=func.now(), updated_at=func.now())
                .execution_options(synchronize_session=False)
            )
            cursor_result = cast("CursorResult[tuple[object, ...]]", update_result)
            unread_result = await session.execute(
                select(func.count(Notification.id)).where(
                    Notification.recipient_id == recipient_id,
                    Notification.active(),
                    Notification.read_at.is_(None),
                )
            )
            result = MarkAllNotificationsReadResult(
                updated_count=cursor_result.rowcount,
                unread_count=unread_result.scalar_one(),
            )
            await session.commit()
            return result
