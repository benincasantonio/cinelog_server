from pydantic import EmailStr, Field
from datetime import date
from typing import Optional

from app.schemas.base_schema import BaseSchema


class UserCreateRequest(BaseSchema):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(...)
    handle: str = Field(None, min_length=3, max_length=20)
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    date_of_birth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    firebase_uid: Optional[str] = Field(None, description="Firebase UID (deprecated, for reference)")
    password_hash: Optional[str] = Field(None, description="Hashed password for local auth")


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
    date_of_birth: date
    firebase_uid: Optional[str] = None
