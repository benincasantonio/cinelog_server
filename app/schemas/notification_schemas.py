"""Notification request, response, and internal persistence schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.base_schemas import BaseSchema
from app.types import NotificationAction, NotificationType

MAX_CURSOR_LENGTH = 512


class StrictNotificationSchema(BaseSchema):
    """Base schema for closed notification contracts."""

    model_config = ConfigDict(extra="forbid")


class BasicUserSummary(StrictNotificationSchema):
    """Public actor fields embedded in a notification response."""

    handle: str
    first_name: str
    last_name: str


class NotificationBaseResponse(StrictNotificationSchema):
    """Common notification presentation and history fields."""

    id: UUID
    type: NotificationType
    title: str
    body: str
    actor: BasicUserSummary | None
    available_actions: list[NotificationAction]
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse[NotificationResponseT: NotificationBaseResponse](StrictNotificationSchema):
    """Cursor-paginated notification inbox response."""

    items: list[NotificationResponseT]
    next_cursor: str | None
    unread_count: int


class MarkAllNotificationsReadResponse(StrictNotificationSchema):
    """Result of marking every active unread notification as read."""

    updated_count: int
    unread_count: int


class NotificationListRequest(StrictNotificationSchema):
    """Validated notification list query parameters."""

    unread_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_LENGTH)


class NotificationCreateData(StrictNotificationSchema):
    """Internal typed input for notification persistence."""

    recipient_id: UUID
    actor_id: UUID | None = None
    type: NotificationType
    title: str
    body: str
    deduplication_key: str | None = None
