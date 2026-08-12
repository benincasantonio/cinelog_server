"""Business rules for basic public-profile following."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from app.config.notification_config import FOLLOW_STARTED_NOTIFICATION_COOLDOWN_SECONDS
from app.models.user_model import User
from app.repository.follow_repository_protocol import FollowRepositoryProtocol
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.schemas.notification_schemas import NotificationCreateData
from app.services.notification_service import NotificationService
from app.types import NotificationType
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException

logger = logging.getLogger(__name__)


class FollowService:
    """Apply public-target eligibility and idempotent follow mutations."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        follow_repository: FollowRepositoryProtocol,
        notification_service: NotificationService | None = None,
    ):
        self.user_repository = user_repository
        self.follow_repository = follow_repository
        self.notification_service = notification_service or NotificationService()

    async def follow_user(self, follower_id: UUID, handle: str) -> None:
        """Follow an active public target, or keep an existing edge unchanged."""

        follower = await self.user_repository.find_user_by_id(follower_id)
        if follower is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        target = await self.user_repository.find_user_by_handle(handle.strip())
        if target is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        if target.id == follower.id:
            raise AppException(ErrorCodes.SELF_FOLLOW_NOT_ALLOWED)

        if await self.follow_repository.is_following(follower.id, target.id):
            return

        if target.profile_visibility != "public":
            raise AppException(ErrorCodes.PROFILE_NOT_PUBLIC)

        await self.follow_repository.create_follow(follower.id, target.id)
        await self._notify_follow_started(actor=follower, recipient=target)

    async def unfollow_user(self, follower_id: UUID, handle: str) -> None:
        """Unfollow an active target regardless of its current visibility."""

        follower = await self.user_repository.find_user_by_id(follower_id)
        if follower is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        target = await self.user_repository.find_user_by_handle(handle.strip())
        if target is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        await self.follow_repository.delete_follow(follower.id, target.id)

    async def _notify_follow_started(self, *, actor: User, recipient: User) -> None:
        """Emit a follow.started inbox row without failing the follow mutation."""

        try:
            await self.notification_service.create_notification(
                NotificationCreateData(
                    recipient_id=recipient.id,
                    actor_id=actor.id,
                    type=NotificationType.FOLLOW_STARTED,
                    title="New follower",
                    body=f"{actor.first_name} {actor.last_name} started following you.",
                    deduplication_key=self._follow_started_deduplication_key(actor.id),
                ),
                cooldown_key=self._follow_started_cooldown_key(recipient.id, actor.id),
                cooldown_seconds=FOLLOW_STARTED_NOTIFICATION_COOLDOWN_SECONDS,
            )
        except Exception:
            logger.exception(
                "Failed to emit follow.started notification for recipient_id=%s actor_id=%s",
                recipient.id,
                actor.id,
            )

    @staticmethod
    def _follow_started_cooldown_key(recipient_id: UUID, actor_id: UUID) -> str:
        return f"cinelog:notif:follow-started:{recipient_id}:{actor_id}"

    @staticmethod
    def _follow_started_deduplication_key(actor_id: UUID) -> str:
        iso_week = datetime.now(UTC).strftime("%G-W%V")
        return f"follow.started:{actor_id}:{iso_week}"
