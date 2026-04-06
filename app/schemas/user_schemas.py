from pydantic import EmailStr, Field
from datetime import date
from typing import Optional

from app.schemas.base_schema import BaseSchema
from app.types import (
    BioStr,
    HandleStr,
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
    password_hash: Optional[str] = Field(
        None, description="Hashed password for local auth"
    )
    profile_visibility: str = Field(
        default="private", description="Profile visibility setting"
    )


class UserCreateResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: date
    profile_visibility: ProfileVisibilityStr = Field(
        ..., description="Profile visibility setting"
    )


class UserResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    profile_visibility: ProfileVisibilityStr = Field(
        ..., description="Profile visibility setting"
    )


class UpdateProfileRequest(BaseSchema):
    first_name: NameStr | None = Field(None, description="User's first name")
    last_name: NameStr | None = Field(None, description="User's last name")
    bio: BioStr = Field(None, description="User biography")
    date_of_birth: Optional[date] = Field(
        None, description="Date of birth in YYYY-MM-DD format"
    )
    profile_visibility: ProfileVisibilityStr | None = Field(
        None, description="Profile visibility setting (public, friends_only, private)"
    )


class UserProfileResponse(BaseSchema):
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    handle: str = Field(..., description="User's unique handle")
    bio: Optional[str] = Field(None, description="User biography")
    profile_visibility: ProfileVisibilityStr = Field(
        ..., description="Profile visibility setting"
    )
    date_of_birth: Optional[date] = Field(
        None,
        description="Date of birth (visible on public profiles or to the profile owner)",
    )


class ChangePasswordRequest(BaseSchema):
    current_password: str = Field(
        ..., min_length=8, max_length=128, description="Current password"
    )
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )


class ChangePasswordResponse(BaseSchema):
    message: str = Field(..., description="Password change confirmation message")
