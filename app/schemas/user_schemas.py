from pydantic import EmailStr, Field, field_validator
from datetime import date
from typing import Optional

from app.schemas.base_schema import BaseSchema
from app.utils.sanitize_utils import strip_html_tags, NAME_PATTERN, HANDLE_PATTERN


class UserCreateRequest(BaseSchema):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(...)
    handle: Optional[str] = Field(None, min_length=3, max_length=20)
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    password_hash: Optional[str] = Field(
        None, description="Hashed password for local auth"
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not NAME_PATTERN.match(v):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("handle")
    @classmethod
    def validate_handle(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
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


class UserCreateResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: date


class UserResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    firebase_uid: Optional[str] = None
