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
    firebase_uid: str = Field(None, description="Firebase UID for the user")
    password_hash: Optional[str] = Field(None, description="Hashed password for local auth")


class UserCreateResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: date


class FirebaseUserData(BaseSchema):
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    email_verified: bool = False
    disabled: bool = False


class UserResponse(BaseSchema):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    date_of_birth: date
    firebase_uid: Optional[str] = None
    firebase_data: Optional[FirebaseUserData] = None
