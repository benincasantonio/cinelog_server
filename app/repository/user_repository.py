"""PostgreSQL user repository implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select

from app.models.user_model import User
from app.repository.repository_base import RepositoryBase
from app.schemas.user_schemas import UserCreateRequest

ALLOWED_PROFILE_FIELDS = {
    "first_name",
    "last_name",
    "bio",
    "profile_visibility",
    "date_of_birth",
}


class UserRepository(RepositoryBase):
    """Repository class for PostgreSQL user-related operations."""

    async def create_user(self, request: UserCreateRequest) -> User:
        """Create a new user in PostgreSQL."""

        if request.handle is None:
            raise ValueError("User handle is required.")

        async with self._session_provider() as session:
            user = User(
                email=request.email,
                handle=request.handle,
                first_name=request.first_name,
                last_name=request.last_name,
                bio=request.bio,
                profile_visibility=request.profile_visibility,
                date_of_birth=request.date_of_birth,
                password_hash=request.password_hash,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def find_user_by_email(self, email: str) -> User | None:
        """Find an active user by email, case-insensitively."""

        async with self._session_provider() as session:
            statement = select(User).where(
                func.lower(User.email) == email.lower(),
                User.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_user_by_handle(self, handle: str) -> User | None:
        """Find an active user by handle, case-insensitively."""

        async with self._session_provider() as session:
            statement = select(User).where(
                func.lower(User.handle) == handle.lower(),
                User.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_user_by_email_or_handle(self, email_or_handle: str) -> User | None:
        """Find an active user by case-insensitive email or handle."""

        async with self._session_provider() as session:
            statement = select(User).where(
                or_(
                    func.lower(User.email) == email_or_handle.lower(),
                    func.lower(User.handle) == email_or_handle.lower(),
                ),
                User.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def find_user_by_id(self, user_id: UUID) -> User | None:
        """Find an active user by UUID."""

        async with self._session_provider() as session:
            statement = select(User).where(
                User.id == user_id,
                User.active(),
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def delete_user(self, user_id: UUID) -> bool:
        """Soft-delete an active user by UUID."""

        async with self._session_provider() as session:
            statement = select(User).where(
                User.id == user_id,
                User.active(),
            )
            result = await session.execute(statement)
            user = result.scalar_one_or_none()
            if user is None:
                return False

            user.deleted = True
            user.deleted_at = datetime.now(UTC)
            user.updated_at = datetime.now(UTC)
            await session.commit()
            return True

    async def delete_user_oblivion(self, user_id: UUID) -> bool:
        """Obliterate user PII and soft-delete the active row."""

        async with self._session_provider() as session:
            statement = select(User).where(
                User.id == user_id,
                User.active(),
            )
            result = await session.execute(statement)
            user = result.scalar_one_or_none()
            if user is None:
                return False

            user.first_name = "Deleted"
            user.last_name = "User"
            user.email = f"deleted_{user_id}@deleted.local"
            user.handle = f"deleted_{user_id}"
            user.bio = None
            user.password_hash = None
            user.reset_password_code = None
            user.reset_password_expires = None
            user.date_of_birth = None
            user.deleted = True
            user.deleted_at = datetime.now(UTC)
            user.updated_at = datetime.now(UTC)
            await session.commit()
            return True

    async def update_password(self, user: User, password_hash: str) -> User:
        """Update password hash for the active user row."""

        async with self._session_provider() as session:
            persisted_user = await session.get(User, user.id)
            if persisted_user is None or persisted_user.deleted:
                raise LookupError("User not found.")

            persisted_user.password_hash = password_hash
            persisted_user.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(persisted_user)
            return persisted_user

    async def set_reset_password_code(
        self,
        user: User,
        code: str,
        expires_at: datetime,
    ) -> User:
        """Persist password-reset metadata for the active user row."""

        async with self._session_provider() as session:
            persisted_user = await session.get(User, user.id)
            if persisted_user is None or persisted_user.deleted:
                raise LookupError("User not found.")

            persisted_user.reset_password_code = code
            persisted_user.reset_password_expires = expires_at
            persisted_user.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(persisted_user)
            return persisted_user

    async def clear_reset_password_code(self, user: User) -> User:
        """Clear password-reset metadata for the active user row."""

        async with self._session_provider() as session:
            persisted_user = await session.get(User, user.id)
            if persisted_user is None or persisted_user.deleted:
                raise LookupError("User not found.")

            persisted_user.reset_password_code = None
            persisted_user.reset_password_expires = None
            persisted_user.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(persisted_user)
            return persisted_user

    async def update_user_profile(self, user_id: UUID, update_data: dict[str, Any]) -> User | None:
        """Update whitelisted profile fields for the active user row."""

        filtered_updates = {field: value for field, value in update_data.items() if field in ALLOWED_PROFILE_FIELDS}
        if not filtered_updates:
            return await self.find_user_by_id(user_id)

        async with self._session_provider() as session:
            statement = select(User).where(
                User.id == user_id,
                User.active(),
            )
            result = await session.execute(statement)
            user = result.scalar_one_or_none()
            if user is None:
                return None

            for field, value in filtered_updates.items():
                setattr(user, field, value)

            user.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(user)
            return user
