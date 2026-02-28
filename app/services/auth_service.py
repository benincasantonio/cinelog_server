from datetime import datetime, timedelta, timezone
import secrets

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import (
    RegisterRequest,
    RegisterResponse,
)
from app.schemas.user_schemas import UserCreateRequest
from app.services.password_service import PasswordService
from app.services.token_service import TokenService
from app.services.email_service import EmailService
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException


class AuthService:
    user_repository: UserRepository
    email_service: EmailService

    def __init__(
        self,
        user_repository: UserRepository,
        email_service: EmailService | None = None,
    ):
        self.user_repository = user_repository
        self.email_service = email_service or EmailService()

    def register(self, request: RegisterRequest) -> RegisterResponse:
        """
        Register a new user in MongoDB.
        """
        # Check if email already exists in MongoDB
        email_lowercase = request.email.strip().lower()
        existing_user_by_email = self.user_repository.find_user_by_email(
            email_lowercase
        )
        if existing_user_by_email:
            raise AppException(ErrorCodes.EMAIL_ALREADY_EXISTS)

        # Check if handle already exists in MongoDB
        existing_user_by_handle = self.user_repository.find_user_by_handle(
            request.handle.strip()
        )
        if existing_user_by_handle:
            raise AppException(ErrorCodes.HANDLE_ALREADY_TAKEN)

        # Hash password
        hashed_password = PasswordService.get_password_hash(request.password.strip())

        # Create user in MongoDB
        try:
            user_create_request = UserCreateRequest(
                first_name=request.first_name,
                last_name=request.last_name,
                email=email_lowercase,
                handle=request.handle.strip(),
                bio=request.bio,
                date_of_birth=request.date_of_birth,
                password_hash=hashed_password,
            )
            user = self.user_repository.create_user(request=user_create_request)
        except Exception as e:
            raise AppException(ErrorCodes.ERROR_CREATING_USER) from e

        response: RegisterResponse = RegisterResponse(
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            handle=user.handle,
            bio=user.bio,
            user_id=str(user.id),
        )

        return response

    def login(self, email: str, password: str):
        """
        Authenticate user and return user object if successful.
        """
        email_lowercase = email.strip().lower()
        user = self.user_repository.find_user_by_email(email_lowercase)
        
        if not user:
            raise AppException(ErrorCodes.INVALID_CREDENTIALS)
            
        # Check migration status
        if not user.password_hash:
            # User exists but has no password hash -> Legacy Firebase user
            # In a real app we might return a specific error code to trigger a frontend flow
            # For now, let's treat it as invalid credentials or a specific migration error if defined
            # The plan says: "Account migration required. Please reset your password."
            # We can use INVALID_CREDENTIALS with a custom message or a new error code.
            # Let's use a generic generic credential error for security, or specific if UX demands it.
            # Given the plan, let's Raise a clear error.
            raise AppException(ErrorCodes.INVALID_CREDENTIALS) 

        if not PasswordService.verify_password(password, user.password_hash):
            raise AppException(ErrorCodes.INVALID_CREDENTIALS)

        return user

    def forgot_password(self, email: str):
        """
        Generate reset code and send email (mocked).
        """
        email_lowercase = email.strip().lower()
        user = self.user_repository.find_user_by_email(email_lowercase)
        if not user:
            # Security: Don't reveal if user exists. 
            # But for migration UX, maybe we return success anyway.
            return

        # Generate 6-digit code
        reset_code = secrets.token_hex(3).upper() # 6 chars
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        self.user_repository.set_reset_password_code(user, reset_code, expires_at)
        
        # Send email via EmailService
        self.email_service.send_reset_password_email(email_lowercase, reset_code)

    def reset_password(self, email: str, code: str, new_password: str):
        """
        Verify reset code and set new password.
        """
        email_lowercase = email.strip().lower()
        user = self.user_repository.find_user_by_email(email_lowercase)
        if not user:
             raise AppException(ErrorCodes.INVALID_CREDENTIALS)
        
        if not user.reset_password_code or user.reset_password_code != code:
             raise AppException(ErrorCodes.INVALID_CREDENTIALS)
             
        if user.reset_password_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
             raise AppException(ErrorCodes.INVALID_CREDENTIALS) # Expired

        hashed_password = PasswordService.get_password_hash(new_password.strip())
        self.user_repository.update_password(user, hashed_password)
        self.user_repository.clear_reset_password_code(user)

        return True
