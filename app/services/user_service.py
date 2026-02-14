from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserResponse, FirebaseUserData
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


class UserService:
    user_repository: UserRepository

    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repository = user_repository

    def get_user_info(self, user_id: str) -> UserResponse:
        """
        Get user information from MongoDB.
        """
        user = self.user_repository.find_user_by_id(user_id)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        return UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            date_of_birth=user.date_of_birth,
            firebase_uid=user.firebase_uid,
            firebase_data=None # Legacy field, can be removed from schema later
        )
