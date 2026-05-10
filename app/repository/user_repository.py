import re
from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId

from app.models.user import User
from app.schemas.user_schemas import UserCreateRequest
from app.utils.object_id_utils import to_object_id


class UserRepository:
    """Repository class for User-related operations."""

    async def create_user(self, request: UserCreateRequest) -> User:
        """Create a new user in the database."""

        # Convert Pydantic model to dict and unpack into User model
        user_data = request.model_dump()

        user = User(**user_data)
        await user.insert()
        return user

    async def find_user_by_email(self, email: str) -> User | None:
        """Find a user by email (case-insensitive)."""
        return await User.find_one(User.active_filter({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}))

    async def find_user_by_handle(self, handle: str) -> User | None:
        """Find a user by handle."""
        return await User.find_one(User.active_filter({"handle": handle}))

    async def find_user_by_email_or_handle(self, email_or_handle: str) -> User | None:
        """Find a user by email or handle."""
        return await self.find_user_by_email(email_or_handle) or await self.find_user_by_handle(email_or_handle)

    async def find_user_by_id(self, user_id: PydanticObjectId) -> User | None:
        """Find a user by ID."""
        parsed_user_id = to_object_id(user_id)
        if parsed_user_id is None:
            return None
        return await User.find_one(User.active_filter({"_id": parsed_user_id}))

    async def delete_user(self, user_id: PydanticObjectId) -> bool:
        """Delete a user logically by ID."""
        user = await self.find_user_by_id(user_id)
        if not user:
            return False

        user.deleted = True
        user.deleted_at = datetime.now(UTC)

        await user.save()
        return True

    async def delete_user_oblivion(self, user_id: PydanticObjectId) -> bool:
        """Obscure all the user information and delete the user logically."""
        user = await self.find_user_by_id(user_id)
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

    async def update_password(self, user: User, password_hash: str) -> User:
        """Update user password."""
        user.password_hash = password_hash
        await user.save()
        return user

    async def set_reset_password_code(self, user: User, code: str, expires_at: datetime) -> User:
        """Set reset password code and expiration."""
        user.reset_password_code = code
        user.reset_password_expires = expires_at
        await user.save()
        return user

    async def clear_reset_password_code(self, user: User) -> User:
        """Clear reset password code."""
        user.reset_password_code = None
        user.reset_password_expires = None
        await user.save()
        return user

    async def update_user_profile(self, user_id: PydanticObjectId, update_data: dict[str, Any]) -> User | None:
        """Update user profile fields."""
        user = await self.find_user_by_id(user_id)
        if not user:
            return None
        for field, value in update_data.items():
            setattr(user, field, value)
        await user.save()
        return user
