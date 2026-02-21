from app.models.user import User
from app.schemas.user_schemas import UserCreateRequest
from datetime import datetime, UTC


class UserRepository:
    """Repository class for User-related operations."""

    @staticmethod
    def create_user(request: UserCreateRequest) -> User:
        """Create a new user in the database."""

        # Convert Pydantic model to dict and unpack into User model
        user_data = request.model_dump()
        
        user = User(**user_data)
        user.save()
        return user

    @staticmethod
    def find_user_by_email(email: str) -> User:
        """Find a user by email (case-insensitive)."""
        return User.objects(email__iexact=email).first()

    @staticmethod
    def find_user_by_handle(handle: str) -> User:
        """Find a user by handle."""
        return User.objects(handle=handle).first()

    @staticmethod
    def find_user_by_email_or_handle(email_or_handle: str) -> User:
        """Find a user by email or handle."""
        return UserRepository.find_user_by_email(
            email_or_handle
        ) or UserRepository.find_user_by_handle(email_or_handle)

    @staticmethod
    def find_user_by_id(user_id: str) -> User:
        """Find a user by ID."""
        return User.objects(id=user_id).first()






    @staticmethod
    def delete_user(user_id: str) -> bool:
        """Delete a user logically by ID."""
        user = UserRepository.find_user_by_id(user_id)

        user.deleted = True
        user.deleted_at = datetime.now(UTC)

        user.save()
        return True

    @staticmethod
    def delete_user_oblivion(user_id: str) -> bool:
        """Obscure all the user information and delete the user logically."""
        user = UserRepository.find_user_by_id(user_id)

        user.first_name = "Deleted"
        user.last_name = "User"
        user.email = ""
        user.handle = f"deleted_{user_id}"
        user.date_of_birth = None
        user.deleted = True
        user.deleted_at = datetime.now(UTC)
        user.save()

        return True

    @staticmethod
    def update_password(user: User, password_hash: str) -> User:
        """Update user password."""
        user.password_hash = password_hash
        user.save()
        return user

    @staticmethod
    def set_reset_password_code(user: User, code: str, expires_at: datetime) -> User:
        """Set reset password code and expiration."""
        user.reset_password_code = code
        user.reset_password_expires = expires_at
        user.save()
        return user

    @staticmethod
    def clear_reset_password_code(user: User) -> User:
        """Clear reset password code."""
        user.reset_password_code = None
        user.reset_password_expires = None
        user.save()
        return user
