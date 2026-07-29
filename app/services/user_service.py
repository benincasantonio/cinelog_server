from datetime import date, datetime
from uuid import UUID

from app.models.user_model import User
from app.repository.follow_repository_protocol import FollowRepositoryProtocol, FollowSummary
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.schemas.user_schemas import (
    ChangePasswordResponse,
    UpdateLocaleResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)
from app.services.password_service import PasswordService
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class UserService:
    user_repository: UserRepositoryProtocol
    follow_repository: FollowRepositoryProtocol

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        follow_repository: FollowRepositoryProtocol,
    ):
        self.user_repository = user_repository
        self.follow_repository = follow_repository

    async def get_user_info(self, user_id: UUID) -> UserResponse:
        """
        Get user information.
        """
        user = await self.user_repository.find_user_by_id(user_id)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        date_of_birth = user.date_of_birth.date() if isinstance(user.date_of_birth, datetime) else user.date_of_birth

        return UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            date_of_birth=date_of_birth,
            locale=user.locale,
            profile_visibility=user.profile_visibility,
        )

    async def get_visible_profile(self, handle: str, requester_id: UUID) -> UserProfileResponse:
        user = await self.user_repository.find_user_by_handle(handle.strip())
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        follow_summary = await self.follow_repository.get_follow_summary(user.id, requester_id)
        is_owner = str(user.id) == str(requester_id)

        if is_owner or user.profile_visibility == "public":
            date_of_birth = (
                user.date_of_birth.date() if isinstance(user.date_of_birth, datetime) else user.date_of_birth
            )
        else:
            date_of_birth = None

        return self._to_profile_response(user, date_of_birth, follow_summary)

    @staticmethod
    def _to_profile_response(
        user: User,
        date_of_birth: date | None,
        follow_summary: FollowSummary,
    ) -> UserProfileResponse:
        """Map a visible user and aggregate follow state to the profile schema."""

        return UserProfileResponse(
            first_name=user.first_name,
            last_name=user.last_name,
            handle=user.handle,
            bio=user.bio,
            profile_visibility=user.profile_visibility,
            date_of_birth=date_of_birth,
            follower_count=follow_summary.follower_count,
            following_count=follow_summary.following_count,
            is_following=follow_summary.is_following,
        )

    async def update_profile(self, user_id: UUID, request: UpdateProfileRequest) -> UserResponse:
        """
        Update user profile fields.
        """
        update_data = request.model_dump(exclude_none=True)
        if not update_data:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        user = await self.user_repository.update_user_profile(user_id, update_data)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        date_of_birth = user.date_of_birth.date() if isinstance(user.date_of_birth, datetime) else user.date_of_birth

        return UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            date_of_birth=date_of_birth,
            locale=user.locale,
            profile_visibility=user.profile_visibility,
        )

    async def update_locale(self, user_id: UUID, locale: str) -> UpdateLocaleResponse:
        """Update the user's preferred locale."""

        user = await self.user_repository.update_user_locale(user_id, locale)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        return UpdateLocaleResponse(locale=user.locale)

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> ChangePasswordResponse:
        """
        Change user password.
        """
        user = await self.user_repository.find_user_by_id(user_id)
        if not user or not user.password_hash:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        if not PasswordService.verify_password(current_password, user.password_hash):
            raise AppException(ErrorCodes.INVALID_CURRENT_PASSWORD)

        if PasswordService.verify_password(new_password, user.password_hash):
            raise AppException(ErrorCodes.SAME_PASSWORD)

        hashed_password = PasswordService.get_password_hash(new_password)
        await self.user_repository.update_password(user, hashed_password)

        return ChangePasswordResponse(message="Password changed successfully")
