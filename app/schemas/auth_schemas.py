from pydantic import EmailStr, Field, field_validator
from datetime import date
from typing import Optional

from app.schemas.base_schema import BaseSchema
from app.utils.sanitize_utils import strip_html_tags, NAME_PATTERN, HANDLE_PATTERN


class RegisterRequest(BaseSchema):
    """Schema for user registration request"""

    first_name: str = Field(
        ..., min_length=1, max_length=50, description="User's first name"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=50, description="User's last name"
    )
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="User's password"
    )
    handle: str = Field(
        ..., min_length=3, max_length=20, description="User's unique handle"
    )
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not NAME_PATTERN.match(v):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("handle")
    @classmethod
    def validate_handle(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Handle must not be empty or whitespace")
        if v[0].isdigit():
            raise ValueError("Handle must not start with a number")
        if not HANDLE_PATTERN.match(v):
            raise ValueError(
                "Handle must contain only alphanumeric characters or underscores"
            )
        return v

    @field_validator("bio")
    @classmethod
    def sanitize_bio(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return strip_html_tags(v)


class RegisterResponse(BaseSchema):
    """Schema for user registration response"""

    user_id: str = Field(..., description="User's unique identifier")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    handle: str = Field(..., description="User's unique handle")
    bio: Optional[str] = Field(None, description="User biography")


class LoginRequest(BaseSchema):
    """Schema for user login request"""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class LoginResponse(BaseSchema):
    """Schema for user login response"""

    user_id: str = Field(..., description="User's unique identifier")
    email: EmailStr = Field(..., description="User's email address")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    handle: str = Field(..., description="User's unique handle")
    bio: Optional[str] = Field(None, description="User biography")
    csrf_token: str = Field(..., description="CSRF token for subsequent requests")


class LogoutResponse(BaseSchema):
    """Schema for user logout response"""

    message: str = Field(..., description="Logout confirmation message")


class RefreshResponse(BaseSchema):
    """Schema for token refresh response"""

    message: str = Field(..., description="Refresh confirmation message")
    csrf_token: str = Field(..., description="New CSRF token for subsequent requests")


class ForgotPasswordRequest(BaseSchema):
    """Schema for forgot password request"""

    email: EmailStr = Field(..., description="User's email address")


class ForgotPasswordResponse(BaseSchema):
    """Schema for forgot password response"""

    message: str = Field(..., description="Forgot password confirmation message")


class ResetPasswordRequest(BaseSchema):
    """Schema for reset password request"""

    email: EmailStr = Field(..., description="User's email address")
    code: str = Field(..., description="Password reset code")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )


class ResetPasswordResponse(BaseSchema):
    """Schema for reset password response"""

    message: str = Field(..., description="Reset password confirmation message")


class CsrfTokenResponse(BaseSchema):
    """Schema for CSRF token response"""

    csrf_token: str = Field(..., description="CSRF token for subsequent requests")
