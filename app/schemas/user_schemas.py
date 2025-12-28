from pydantic import BaseModel, EmailStr, Field
from datetime import date
from typing import Optional


class UserCreateRequest(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=50)
    lastName: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(...)
    handle: str = Field(None, min_length=3, max_length=20)
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    dateOfBirth: date = Field(..., description="Date of birth in YYYY-MM-DD format")
    firebaseUid: str = Field(None, description="Firebase UID for the user")


class UserCreateResponse(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    dateOfBirth: date


from typing import Optional


class FirebaseUserData(BaseModel):
    email: Optional[str] = None
    displayName: Optional[str] = None
    photoUrl: Optional[str] = None
    emailVerified: bool = False
    disabled: bool = False


class UserResponse(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: EmailStr
    handle: str
    bio: Optional[str] = None
    dateOfBirth: date
    firebaseUid: Optional[str] = None
    firebaseData: Optional[FirebaseUserData] = None
