from datetime import date

from pydantic import EmailStr, Field

from app.schemas.base_schemas import BaseSchema
from app.types import BioStr, HandleStr, LocaleStr, NameStr, NewPasswordStr, ProfileVisibilityStr


class RegisterRequest(BaseSchema):
    """Schema for user registration request"""

    first_name: NameStr = Field(description="User's first name")
    last_name: NameStr = Field(description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    password: NewPasswordStr = Field(description="User's password: 8–72 characters, at most 72 UTF-8 bytes")
    handle: HandleStr = Field(description="User's unique handle")
    bio: BioStr = Field(None, description="User biography")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    locale: LocaleStr = Field(..., description="User's preferred locale")
    profile_visibility: ProfileVisibilityStr = Field(
        default="private",
        description="Profile visibility setting (public, followers_only, private)",
    )
    verification_code: str | None = Field(
        None,
        description="Email verification code; required at runtime to create an account",
    )


class RegisterSendCodeRequest(BaseSchema):
    """Schema for registration email verification request"""

    email: EmailStr = Field(..., description="User's email address")


class RegisterSendCodeResponse(BaseSchema):
    """Schema for registration email verification response"""

    message: str = Field(..., description="Registration email verification confirmation message")


class RegisterResponse(BaseSchema):
    """Schema for user registration response"""

    user_id: str = Field(..., description="User's unique identifier")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    handle: str = Field(..., description="User's unique handle")
    bio: str | None = Field(None, description="User biography")
    locale: LocaleStr = Field(..., description="User's preferred locale")
    profile_visibility: ProfileVisibilityStr = Field(
        ...,
        description="Profile visibility setting (public, followers_only, private)",
    )


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
    bio: str | None = Field(None, description="User biography")
    locale: LocaleStr = Field(..., description="User's preferred locale")
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
    new_password: NewPasswordStr = Field(description="New password: 8–72 characters, at most 72 UTF-8 bytes")


class ResetPasswordResponse(BaseSchema):
    """Schema for reset password response"""

    message: str = Field(..., description="Reset password confirmation message")


class CsrfTokenResponse(BaseSchema):
    """Schema for CSRF token response"""

    csrf_token: str = Field(..., description="CSRF token for subsequent requests")
