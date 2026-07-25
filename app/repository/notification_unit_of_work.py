"""Cross-repository transaction seam: notification creation plus its outbound deliveries.

Opens one session, creates the notification, enqueues one outbound message per
requested channel, and commits atomically — a notification is never persisted
without an attempt to queue its deliveries, and a failed enqueue rolls the
notification back too. This class deliberately composes a repository and a service:
it is the transaction seam, not a single-table repository. #198 extends it to bind
the follow repository into the same transaction.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_async_session
from app.repository.notification_repository_protocol import (
    NotificationCreateResult,
    NotificationRepositoryProtocol,
)
from app.schemas.notification_schemas import NotificationCreateData
from app.services.outbound_message_service import OutboundMessageService
from app.types import OutboundMessageChannel


class NotificationUnitOfWork:
    """Create a notification and enqueue its outbound deliveries in one transaction."""

    def __init__(
        self,
        notification_repository: NotificationRepositoryProtocol,
        outbound_message_service: OutboundMessageService,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]] = get_async_session,
    ):
        self.notification_repository = notification_repository
        self.outbound_message_service = outbound_message_service
        self._session_provider = session_provider

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[AsyncSession]:
        async with self._session_provider() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    async def create_notification_with_deliveries(
        self,
        data: NotificationCreateData,
        *,
        channels: tuple[OutboundMessageChannel, ...] = (OutboundMessageChannel.EMAIL,),
    ) -> NotificationCreateResult:
        """Create the notification and enqueue one outbound message per channel, atomically.

        Always attempts the enqueue, even when the notification already existed
        (``created is False``): the unique ``(notification_id, channel)`` constraint plus
        ``ON CONFLICT DO NOTHING`` makes a duplicate enqueue a database-level no-op, so a
        notification that is somehow missing its message self-heals on retry.
        """

        async with self._transaction() as session:
            result = await self.notification_repository.create_notification(data, session=session)
            for channel in channels:
                if channel is OutboundMessageChannel.EMAIL:
                    await self.outbound_message_service.enqueue_notification_email(result.notification, session=session)
                else:
                    raise ValueError(f"No outbound delivery handler registered for channel {channel!r}")
            return result
