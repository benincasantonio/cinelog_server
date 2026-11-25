"""Business rules for basic public-profile following."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres import get_async_session
from app.repository.follow_repository_protocol import FollowRepositoryProtocol
from app.repository.notification_repository_protocol import NotificationCreateResult, NotificationRepositoryProtocol
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.schemas.notification_schemas import NotificationCreateData
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
        notification_repository: NotificationRepositoryProtocol,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]] = get_async_session,
    ):
        self.user_repository = user_repository
        self.follow_repository = follow_repository
        self.notification_repository = notification_repository
        self._session_provider = session_provider

    async def follow_user(self, follower_id: UUID, handle: str) -> NotificationCreateResult | None:
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
            return None

        if target.profile_visibility != "public":
            raise AppException(ErrorCodes.PROFILE_NOT_PUBLIC)

        result = None
        try:
            async with self._session_provider() as session:
                async with session.begin():
                    created = await self.follow_repository.create_follow(follower.id, target.id, session=session)
                    # The winning insert holds the pair's unique-key protection until commit.
                    if created and not await self.notification_repository.has_recent_follow_started(
                        target.id, follower.id, session=session
                    ):
                        result = await self.notification_repository.create_notification(
                            NotificationCreateData(
                                recipient_id=target.id,
                                actor_id=follower.id,
                                type=NotificationType.FOLLOW_STARTED,
                                title="New follower",
                                body=f"{follower.first_name} {follower.last_name} started following you.",
                            ),
                            session=session,
                        )
        except Exception as exc:
            logger.exception("Failed to persist follow for recipient_id=%s actor_id=%s", target.id, follower.id)
            raise AppException(ErrorCodes.ERROR_CREATING_FOLLOW) from exc
        return result

    async def unfollow_user(self, follower_id: UUID, handle: str) -> None:
        """Unfollow an active target regardless of its current visibility."""

        follower = await self.user_repository.find_user_by_id(follower_id)
        if follower is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        target = await self.user_repository.find_user_by_handle(handle.strip())
        if target is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        await self.follow_repository.delete_follow(follower.id, target.id)
