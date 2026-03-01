from datetime import datetime, UTC
import re

from app.models.user import User
from app.schemas.user_schemas import UserCreateRequest
from app.utils.object_id_utils import to_object_id


class UserRepository:
    """Repository class for User-related operations."""

    @staticmethod
    async def create_user(request: UserCreateRequest) -> User:
        """Create a new user in the database."""

        # Convert Pydantic model to dict and unpack into User model
        user_data = request.model_dump()

        user = User(**user_data)
        await user.insert()
        return user

    @staticmethod
    async def find_user_by_email(email: str) -> User | None:
        """Find a user by email (case-insensitive)."""
        return await User.find_one(
            User.active_filter(
                {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}
            )
        )

    @staticmethod
    async def find_user_by_handle(handle: str) -> User | None:
        """Find a user by handle."""
        return await User.find_one(User.active_filter({"handle": handle}))

    @staticmethod
    async def find_user_by_email_or_handle(email_or_handle: str) -> User | None:
        """Find a user by email or handle."""
        return await UserRepository.find_user_by_email(
            email_or_handle
        ) or await UserRepository.find_user_by_handle(email_or_handle)

    @staticmethod
    async def find_user_by_id(user_id: str) -> User | None:
        """Find a user by ID."""
        parsed_user_id = to_object_id(user_id)
        if parsed_user_id is None:
            return None
        return await User.find_one(User.active_filter({"_id": parsed_user_id}))

    @staticmethod
    async def delete_user(user_id: str) -> bool:
        """Delete a user logically by ID."""
        user = await UserRepository.find_user_by_id(user_id)
        if not user:
            return False

        user.deleted = True
        user.deleted_at = datetime.now(UTC)

        await user.save()
        return True

    @staticmethod
    async def delete_user_oblivion(user_id: str) -> bool:
        """Obscure all the user information and delete the user logically."""
        user = await UserRepository.find_user_by_id(user_id)
        if not user:
            return False

        user.first_name = "Deleted"
        user.last_name = "User"
        user.email = f"deleted_{user_id}@deleted.local"
        user.handle = f"deleted_{user_id}"
        user.password_hash = None
        user.reset_password_code = None
        user.reset_password_expires = None
        user.date_of_birth = None
        user.deleted = True
        user.deleted_at = datetime.now(UTC)
        await user.save()

        return True

    @staticmethod
    async def update_password(user: User, password_hash: str) -> User:
        """Update user password."""
        user.password_hash = password_hash
        await user.save()
        return user

    @staticmethod
    async def set_reset_password_code(
        user: User, code: str, expires_at: datetime
    ) -> User:
        """Set reset password code and expiration."""
        user.reset_password_code = code
        user.reset_password_expires = expires_at
        await user.save()
        return user

    @staticmethod
    async def clear_reset_password_code(user: User) -> User:
        """Clear reset password code."""
        user.reset_password_code = None
        user.reset_password_expires = None
        await user.save()
        return user
