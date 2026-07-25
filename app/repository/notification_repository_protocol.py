"""Protocol and result types for notification persistence."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_model import Notification
from app.schemas.notification_schemas import NotificationCreateData
from app.types import TimestampUUIDCursor


@dataclass(frozen=True)
class NotificationCreateResult:
    """Idempotent notification creation result."""

    notification: Notification
    created: bool


@dataclass(frozen=True)
class NotificationPage:
    """Repository page plus recipient-wide unread metadata."""

    items: Sequence[Notification]
    has_more: bool
    unread_count: int


@dataclass(frozen=True)
class MarkAllNotificationsReadResult:
    """Bulk read-state persistence result."""

    updated_count: int
    unread_count: int


class NotificationRepositoryProtocol(Protocol):
    """Notification repository operations used by services and future producers."""

    async def create_notification(
        self,
        data: NotificationCreateData,
        *,
        session: AsyncSession | None = None,
    ) -> NotificationCreateResult:
        """Create once per active recipient/event key, returning an existing duplicate.

        Accepts an optional ``session`` so a unit of work can join an existing
        transaction rather than opening its own.
        """

    async def list_notifications(
        self,
        recipient_id: UUID,
        *,
        unread_only: bool,
        limit: int,
        cursor: TimestampUUIDCursor | None,
    ) -> NotificationPage:
        """List a stable active page and count all recipient unread rows."""

    async def mark_notification_read(
        self,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> Notification | None:
        """Idempotently mark one owned active notification read."""

    async def mark_all_notifications_read(self, recipient_id: UUID) -> MarkAllNotificationsReadResult:
        """Mark all currently active unread recipient notifications read."""
