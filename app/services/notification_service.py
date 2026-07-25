"""Business logic for the generic in-app notification inbox."""

from collections.abc import Sequence
from uuid import UUID

from app.config.notification_config import notification_list_cursor_scope
from app.models.notification_model import Notification
from app.repository.notification_repository_protocol import (
    NotificationCreateResult,
    NotificationRepositoryProtocol,
)
from app.repository.notification_unit_of_work_protocol import NotificationUnitOfWorkProtocol
from app.schemas.notification_schemas import (
    BasicUserSummary,
    MarkAllNotificationsReadResponse,
    NotificationBaseResponse,
    NotificationCreateData,
    NotificationListRequest,
    NotificationListResponse,
)
from app.types import NotificationType, OutboundMessageChannel, TimestampUUIDCursor
from app.utils.cursor_pagination_utils import (
    decode_timestamp_uuid_cursor,
    encode_timestamp_uuid_cursor,
)
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class NotificationService:
    """Orchestrate recipient-scoped notification persistence and response assembly."""

    def __init__(
        self,
        repository: NotificationRepositoryProtocol,
        unit_of_work: NotificationUnitOfWorkProtocol,
    ) -> None:
        # Both collaborators are injected rather than self-defaulted from the dependency
        # module: a service that imports its own providers forces those providers to live
        # in the repository layer to avoid an import cycle.
        self.repository = repository
        self.unit_of_work = unit_of_work

    @staticmethod
    def _to_response(notification: Notification) -> NotificationBaseResponse:
        """Map one persisted notification to the current common API response."""

        actor = notification.actor
        actor_summary = None
        if actor is not None and not actor.deleted:
            actor_summary = BasicUserSummary(
                handle=actor.handle,
                first_name=actor.first_name,
                last_name=actor.last_name,
            )

        return NotificationBaseResponse(
            id=notification.id,
            type=NotificationType(notification.type),
            title=notification.title,
            body=notification.body,
            actor=actor_summary,
            available_actions=[],
            read_at=notification.read_at,
            created_at=notification.created_at,
        )

    async def create_notification(
        self,
        data: NotificationCreateData,
        *,
        channels: tuple[OutboundMessageChannel, ...] = (OutboundMessageChannel.EMAIL,),
    ) -> NotificationCreateResult:
        """Create a typed notification and enqueue its outbound deliveries atomically."""

        return await self.unit_of_work.create_notification_with_deliveries(data, channels=channels)

    async def list_notifications(
        self,
        recipient_id: UUID,
        request: NotificationListRequest,
    ) -> NotificationListResponse[NotificationBaseResponse]:
        """Return one stable inbox page without mutating read state."""

        scope = notification_list_cursor_scope(recipient_id)
        cursor = self._decode_cursor(request.cursor, scope) if request.cursor is not None else None
        page = await self.repository.list_notifications(
            recipient_id,
            unread_only=request.unread_only,
            limit=request.limit,
            cursor=cursor,
        )
        items = [self._to_response(notification) for notification in page.items]
        next_cursor = self._next_cursor(page.items, page.has_more, scope)
        return NotificationListResponse[NotificationBaseResponse](
            items=items,
            next_cursor=next_cursor,
            unread_count=page.unread_count,
        )

    async def mark_notification_read(
        self,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> NotificationBaseResponse:
        """Idempotently mark one owned notification read and return its persisted state."""

        notification = await self.repository.mark_notification_read(notification_id, recipient_id)
        if notification is None:
            raise AppException(ErrorCodes.NOTIFICATION_NOT_FOUND)

        return self._to_response(notification)

    async def mark_all_notifications_read(self, recipient_id: UUID) -> MarkAllNotificationsReadResponse:
        """Mark all current active unread rows and return recipient-wide counts."""

        result = await self.repository.mark_all_notifications_read(recipient_id)
        return MarkAllNotificationsReadResponse(
            updated_count=result.updated_count,
            unread_count=result.unread_count,
        )

    @staticmethod
    def _decode_cursor(value: str, scope: str) -> TimestampUUIDCursor:
        """Decode a client cursor, converting rejection into the API error contract."""

        try:
            return decode_timestamp_uuid_cursor(value, expected_scope=scope)
        except ValueError as exc:
            raise AppException(ErrorCodes.INVALID_PAGINATION_CURSOR) from exc

    @staticmethod
    def _next_cursor(items: Sequence[Notification], has_more: bool, scope: str) -> str | None:
        if not has_more or not items:
            return None
        last = items[-1]
        return encode_timestamp_uuid_cursor(
            TimestampUUIDCursor(timestamp=last.created_at, id=last.id),
            scope=scope,
        )
