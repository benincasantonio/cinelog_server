from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date

class LoginRequest(BaseModel):
    """Schema for user login request"""
    emailOrHandle: str = Field(..., description="User's email or handle")
    password: str = Field(..., min_length=8, max_length=128, description="User's password")

class LoginResponse(BaseModel):
    """Schema for user login response"""
    access_token: str = Field(..., description="JWT access token")
    user_id: str = Field(..., description="User's unique identifier")
    firstName: str = Field(..., description="User's first name")
    lastName: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    handle: str = Field(..., description="User's unique handle")

class RegisterRequest(BaseModel):
    """Schema for user registration request"""
    firstName: str = Field(..., min_length=1, max_length=50, description="User's first name")
    lastName: str = Field(..., min_length=1, max_length=50, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=128, description="User's password")
    handle: str = Field(..., min_length=3, max_length=20, description="User's unique handle")
    dateOfBirth: date = Field(..., description="Date of birth in YYYY-MM-DD format")

class RegisterResponse(BaseModel):
    """Schema for user registration response"""
    access_token: str = Field(..., description="JWT access token")
    user_id: str = Field(..., description="User's unique identifier")
    firstName: str = Field(..., description="User's first name")
    lastName: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    handle: str = Field(..., description="User's unique handle")
