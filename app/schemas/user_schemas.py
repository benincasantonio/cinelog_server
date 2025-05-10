from pydantic import BaseModel, EmailStr, Field
from datetime import date

class UserCreateRequest(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=50)
    lastName: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8, max_length=128)
    handle: str = Field(None, min_length=3, max_length=20)
    dateOfBirth: date = Field(..., description="Date of birth in YYYY-MM-DD format")

class UserCreateResponse(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: EmailStr
    handle: str
    dateOfBirth: date
