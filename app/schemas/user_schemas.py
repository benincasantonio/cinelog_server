from datetime import date

from pydantic import EmailStr, Field

from app.schemas.base_schemas import BaseSchema
from app.types import (
    BioStr,
    HandleStr,
    LocaleStr,
    NameStr,
    ProfileVisibilityStr,
)


class UserCreateRequest(BaseSchema):
    first_name: NameStr = Field(description="User's first name")
    last_name: NameStr = Field(description="User's last name")
    email: EmailStr = Field(...)
    handle: HandleStr | None = Field(None, description="User's unique handle")
    bio: BioStr = Field(None, description="User biography")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    password_hash: str | None = Field(None, description="Hashed password for local auth")
    locale: LocaleStr = Field(..., description="User's preferred locale")
    profile_visibility: ProfileVisibilityStr = Field(
        default="private",
        description="Profile visibility setting (public, followers_only, private)",
    )


class UserCreateResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: str | None = None
    date_of_birth: date
    locale: LocaleStr = Field(..., description="User's preferred locale")
    profile_visibility: ProfileVisibilityStr = Field(
        ...,
        description="Profile visibility setting (public, followers_only, private)",
    )


class UserResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: str | None = None
    date_of_birth: date | None = None
    locale: LocaleStr = Field(..., description="User's preferred locale")
    profile_visibility: ProfileVisibilityStr = Field(
        ...,
        description="Profile visibility setting (public, followers_only, private)",
    )


class UpdateProfileRequest(BaseSchema):
    first_name: NameStr | None = Field(None, description="User's first name")
    last_name: NameStr | None = Field(None, description="User's last name")
    bio: BioStr = Field(None, description="User biography")
    date_of_birth: date | None = Field(None, description="Date of birth in YYYY-MM-DD format")
    profile_visibility: ProfileVisibilityStr | None = Field(
        None, description="Profile visibility setting (public, followers_only, private)"
    )


class UserProfileResponse(BaseSchema):
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    handle: str = Field(..., description="User's unique handle")
    bio: str | None = Field(None, description="User biography")
    profile_visibility: ProfileVisibilityStr = Field(
        ...,
        description="Profile visibility setting (public, followers_only, private)",
    )
    date_of_birth: date | None = Field(
        None,
        description="Date of birth (visible on public profiles or to the profile owner)",
    )
    follower_count: int = Field(..., ge=0, description="Number of active users following this profile")
    following_count: int = Field(..., ge=0, description="Number of active users this profile follows")
    is_following: bool = Field(
        ...,
        description="Whether the authenticated requester follows this profile",
    )


class ChangePasswordRequest(BaseSchema):
    current_password: str = Field(..., min_length=8, max_length=128, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class ChangePasswordResponse(BaseSchema):
    message: str = Field(..., description="Password change confirmation message")


class UpdateLocaleRequest(BaseSchema):
    locale: LocaleStr = Field(..., description="User's preferred locale")


class UpdateLocaleResponse(BaseSchema):
    locale: LocaleStr = Field(..., description="User's saved preferred locale")
