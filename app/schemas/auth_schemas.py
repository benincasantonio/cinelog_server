from pydantic import BaseModel, EmailStr, Field
from datetime import date
from typing import Optional


class RegisterRequest(BaseModel):
    """Schema for user registration request"""

    firstName: str = Field(
        ..., min_length=1, max_length=50, description="User's first name"
    )
    lastName: str = Field(
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
    dateOfBirth: date = Field(..., description="Date of birth in YYYY-MM-DD format")


class RegisterResponse(BaseModel):
    """Schema for user registration response"""

    user_id: str = Field(..., description="User's unique identifier")
    firstName: str = Field(..., description="User's first name")
    lastName: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    handle: str = Field(..., description="User's unique handle")
    bio: Optional[str] = Field(None, description="User biography")
