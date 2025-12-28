from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository
from app.schemas.auth_schemas import (
    RegisterRequest,
    RegisterResponse,
)
from app.schemas.user_schemas import UserCreateRequest
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException
from app.integrations.firebase import is_firebase_initialized
from firebase_admin import auth


class AuthService:
    user_repository: UserRepository
    firebase_auth_repository: FirebaseAuthRepository

    def __init__(
        self,
        user_repository: UserRepository,
        firebase_auth_repository: FirebaseAuthRepository,
    ):
        self.user_repository = user_repository
        self.firebase_auth_repository = firebase_auth_repository

    def register(self, request: RegisterRequest) -> RegisterResponse:
        """
        Register a new user by creating them in Firebase first, then in MongoDB.

        Args:
            request: Registration request with user details

        Returns:
            RegisterResponse with user information

        Raises:
            AppException: If email/handle already exists or Firebase operations fail
            ValueError: If Firebase is not initialized
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        # Check if email already exists in MongoDB
        existing_user_by_email = self.user_repository.find_user_by_email(
            request.email.strip()
        )
        if existing_user_by_email:
            raise AppException(ErrorCodes.EMAIL_ALREADY_EXISTS)

        # Check if handle already exists in MongoDB
        existing_user_by_handle = self.user_repository.find_user_by_handle(
            request.handle.strip()
        )
        if existing_user_by_handle:
            raise AppException(ErrorCodes.HANDLE_ALREADY_TAKEN)

        # Create user in Firebase first
        firebase_user = None
        try:
            display_name = f"{request.firstName} {request.lastName}".strip()
            firebase_user = self.firebase_auth_repository.create_user(
                email=request.email.strip(),
                password=request.password.strip(),
                display_name=display_name,
                email_verified=False,
                disabled=False,
            )
        except auth.EmailAlreadyExistsError:
            raise AppException(ErrorCodes.EMAIL_ALREADY_EXISTS)
        except Exception as e:
            raise AppException(ErrorCodes.ERROR_CREATING_USER) from e

        # Get Firebase UID
        firebase_uid = firebase_user.uid

        # Create user in MongoDB with Firebase UID
        try:
            user_create_request = UserCreateRequest(
                firstName=request.firstName,
                lastName=request.lastName,
                email=request.email.strip(),
                handle=request.handle.strip(),
                bio=request.bio,
                dateOfBirth=request.dateOfBirth,
                firebaseUid=firebase_uid,
            )
            user = self.user_repository.create_user(request=user_create_request)
        except Exception as e:
            # Rollback: Delete Firebase user if MongoDB creation fails
            try:
                self.firebase_auth_repository.delete_user(firebase_uid)
            except Exception:
                pass  # Log error but don't fail on rollback
            raise AppException(ErrorCodes.ERROR_CREATING_USER) from e

        # For now, return RegisterResponse (token generation may be updated later)
        response: RegisterResponse = RegisterResponse(
            email=user.email,
            firstName=user.firstName,
            lastName=user.lastName,
            handle=user.handle,
            bio=user.bio,
            user_id=user.id.__str__(),
        )

        return response
