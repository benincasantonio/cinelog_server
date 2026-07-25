from datetime import datetime
from typing import Any, Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user_schemas import UserCreateRequest

IdType = TypeVar("IdType", contravariant=True)
UserType = TypeVar("UserType")


class UserRepositoryProtocol(Protocol[IdType, UserType]):
    """Protocol for user repository implementations."""

    async def create_user(self, request: UserCreateRequest) -> UserType:
        """Create a new user in the database."""

    async def find_user_by_email(self, email: str) -> UserType | None:
        """Find a user by email (case-insensitive)."""

    async def find_user_by_handle(self, handle: str) -> UserType | None:
        """Find a user by handle."""

    async def find_user_by_email_or_handle(self, email_or_handle: str) -> UserType | None:
        """Find a user by email or handle."""

    async def find_user_by_id(self, user_id: IdType, *, session: AsyncSession | None = None) -> UserType | None:
        """Find a user by ID, optionally reading through a caller-supplied session."""

    async def delete_user(self, user_id: IdType) -> bool:
        """Delete a user logically by ID."""

    async def delete_user_oblivion(self, user_id: IdType) -> bool:
        """Obscure all the user information and delete the user logically."""

    async def update_password(self, user: UserType, new_password_hash: str) -> UserType:
        """Update a user's password hash."""

    async def set_reset_password_code(self, user: UserType, code: str, expires_at: datetime) -> UserType:
        """Set reset password code and expiration for a user."""

    async def clear_reset_password_code(self, user: UserType) -> UserType:
        """Clear reset password code and expiration for a user."""

    async def update_user_profile(self, user_id: IdType, update_data: dict[str, Any]) -> UserType | None:
        """Update user profile fields."""
