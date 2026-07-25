"""Protocol for the notification-creation-plus-delivery transaction seam."""

from typing import Protocol

from app.repository.notification_repository_protocol import NotificationCreateResult
from app.schemas.notification_schemas import NotificationCreateData
from app.types import OutboundMessageChannel


class NotificationUnitOfWorkProtocol(Protocol):
    """Create a notification and enqueue its outbound deliveries atomically."""

    async def create_notification_with_deliveries(
        self,
        data: NotificationCreateData,
        *,
        channels: tuple[OutboundMessageChannel, ...] = (OutboundMessageChannel.EMAIL,),
    ) -> NotificationCreateResult:
        """Create the notification and enqueue one outbound message per channel.

        Runs in a single transaction: a failed enqueue rolls back the notification too.
        """
