from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository
from app.schemas.user_schemas import UserResponse, FirebaseUserData
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes
from app.integrations.firebase import is_firebase_initialized


class UserService:
    user_repository: UserRepository
    firebase_auth_repository: FirebaseAuthRepository

    def __init__(
        self,
        user_repository: UserRepository,
        firebase_auth_repository: FirebaseAuthRepository,
    ):
        self.user_repository = user_repository
        self.firebase_auth_repository = firebase_auth_repository

    def get_user_info(self, user_id: str) -> UserResponse:
        """
        Get user information from MongoDB and Firebase (if available).
        """
        user = self.user_repository.find_user_by_id(user_id)
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        firebase_data = None
        if user.firebase_uid and is_firebase_initialized():
            try:
                firebase_user = self.firebase_auth_repository.get_user(user.firebase_uid)
                firebase_data = FirebaseUserData(
                    email=firebase_user.email,
                    display_name=firebase_user.display_name,
                    photo_url=firebase_user.photo_url,
                    email_verified=firebase_user.email_verified,
                    disabled=firebase_user.disabled
                )
            except Exception:
                # Log error or silently fail if firebase user not found/error
                pass

        return UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            date_of_birth=user.date_of_birth,
            firebase_uid=user.firebase_uid,
            firebase_data=firebase_data
        )
