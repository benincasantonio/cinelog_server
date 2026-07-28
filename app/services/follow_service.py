"""Business rules for basic public-profile following."""

from uuid import UUID

from app.repository.follow_repository_protocol import FollowRepositoryProtocol
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class FollowService:
    """Apply public-target eligibility and idempotent follow mutations."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        follow_repository: FollowRepositoryProtocol,
    ):
        self.user_repository = user_repository
        self.follow_repository = follow_repository

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

    async def unfollow_user(self, follower_id: UUID, handle: str) -> None:
        """Unfollow an active target regardless of its current visibility."""

        follower = await self.user_repository.find_user_by_id(follower_id)
        if follower is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        target = await self.user_repository.find_user_by_handle(handle.strip())
        if target is None:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        await self.follow_repository.delete_follow(follower.id, target.id)
