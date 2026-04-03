from datetime import datetime

from beanie import PydanticObjectId

from app.repository.log_repository import LogRepository
from app.repository.user_repository import UserRepository
from app.schemas.log_schemas import LogListRequest, LogListResponse
from app.schemas.user_schemas import (
    ChangePasswordResponse,
    PublicProfileResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.log_service import LogService
from app.services.password_service import PasswordService
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException


class UserService:
    user_repository: UserRepository

    def __init__(
        self,
        user_repository: UserRepository,
        log_repository: LogRepository | None = None,
    ):
        self.user_repository = user_repository
        self.log_repository = log_repository

    async def get_user_info(self, user_id: PydanticObjectId) -> UserResponse:
        """
        Get user information from MongoDB.
        """
        user = await self.user_repository.find_user_by_id(user_id)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        date_of_birth = (
            user.date_of_birth.date()
            if isinstance(user.date_of_birth, datetime)
            else user.date_of_birth
        )

        return UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            date_of_birth=date_of_birth,
            profile_visibility=user.profile_visibility,
        )

    async def get_public_profile(
        self, handle: str, requesting_user_id: PydanticObjectId
    ) -> PublicProfileResponse:
        """
        Get a user's public profile by handle, enforcing visibility rules.

        - Own profile: always full access (returns full PublicProfileResponse).
        - Public: full profile accessible.
        - friends_only / private: basic info only (name, handle, bio).
        """
        user = await self.user_repository.find_user_by_handle(handle)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        return PublicProfileResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            handle=user.handle,
            bio=user.bio,
            profile_visibility=user.profile_visibility,
        )

    async def get_public_user_logs(
        self,
        handle: str,
        requesting_user_id: PydanticObjectId,
        request: LogListRequest,
    ) -> LogListResponse:
        """
        Get a user's logs by handle, enforcing visibility rules.

        - Own profile: always full access.
        - Public: logs accessible.
        - friends_only / private: raises PROFILE_NOT_PUBLIC (403).
        """
        assert self.log_repository is not None, "log_repository must be provided"

        user = await self.user_repository.find_user_by_handle(handle)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        is_own_profile = str(user.id) == str(requesting_user_id)

        if not is_own_profile and user.profile_visibility != "public":
            raise AppException(ErrorCodes.PROFILE_NOT_PUBLIC)

        log_service = LogService(self.log_repository)
        return await log_service.get_user_logs(user_id=user.id, request=request)

    async def update_profile(
        self, user_id: PydanticObjectId, request: UpdateProfileRequest
    ) -> UserResponse:
        """
        Update user profile fields.
        """
        update_data = request.model_dump(exclude_none=True)
        if not update_data:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        user = await self.user_repository.update_user_profile(user_id, update_data)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        date_of_birth = (
            user.date_of_birth.date()
            if isinstance(user.date_of_birth, datetime)
            else user.date_of_birth
        )

        return UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            date_of_birth=date_of_birth,
            profile_visibility=user.profile_visibility,
        )

    async def change_password(
        self,
        user_id: PydanticObjectId,
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
