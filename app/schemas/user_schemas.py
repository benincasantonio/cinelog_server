from pydantic import EmailStr, Field
from datetime import date
from typing import Optional

from app.schemas.base_schema import BaseSchema
from app.types import BioStr, NameStr, OptionalHandleStr, OptionalNameStr, ProfileVisibilityStr


class UserCreateRequest(BaseSchema):
    first_name: NameStr = Field(description="User's first name")
    last_name: NameStr = Field(description="User's last name")
    email: EmailStr = Field(...)
    handle: OptionalHandleStr = Field(None, description="User's unique handle")
    bio: BioStr = Field(None, description="User biography")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    password_hash: Optional[str] = Field(
        None, description="Hashed password for local auth"
    )
    profile_visibility: ProfileVisibilityStr = Field(
        "private", description="Profile visibility setting"
    )


class UserCreateResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: date
    profile_visibility: ProfileVisibilityStr


class UserResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    profile_visibility: ProfileVisibilityStr = "private"


class PublicProfileResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    handle: str
    bio: Optional[str] = None
    profile_visibility: ProfileVisibilityStr


class UpdateProfileRequest(BaseSchema):
    first_name: OptionalNameStr = Field(None, description="User's first name")
    last_name: OptionalNameStr = Field(None, description="User's last name")
    bio: BioStr = Field(None, description="User biography")
    date_of_birth: Optional[date] = Field(
        None, description="Date of birth in YYYY-MM-DD format"
    )
    profile_visibility: Optional[ProfileVisibilityStr] = Field(
        None, description="Profile visibility setting"
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
