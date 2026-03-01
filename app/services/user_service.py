from datetime import datetime

from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserResponse
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException


class UserService:
    user_repository: UserRepository

    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repository = user_repository

    async def get_user_info(self, user_id: str) -> UserResponse:
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
        )
