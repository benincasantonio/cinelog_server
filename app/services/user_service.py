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
        if user.firebaseUid and is_firebase_initialized():
            try:
                firebase_user = self.firebase_auth_repository.get_user(user.firebaseUid)
                firebase_data = FirebaseUserData(
                    email=firebase_user.email,
                    displayName=firebase_user.display_name,
                    photoUrl=firebase_user.photo_url,
                    emailVerified=firebase_user.email_verified,
                    disabled=firebase_user.disabled
                )
            except Exception:
                # Log error or silently fail if firebase user not found/error
                pass

        return UserResponse(
            id=str(user.id),
            firstName=user.firstName,
            lastName=user.lastName,
            email=user.email,
            handle=user.handle,
            bio=user.bio,
            dateOfBirth=user.dateOfBirth,
            firebaseUid=user.firebaseUid,
            firebaseData=firebase_data
        )
