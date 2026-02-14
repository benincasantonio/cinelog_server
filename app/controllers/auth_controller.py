from fastapi import APIRouter, Response, Depends, status, HTTPException, Request, Body
from typing import Annotated

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import (
    RegisterRequest,
    RegisterResponse,
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.utils.auth_utils import set_auth_cookies
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException
from datetime import timedelta
from pydantic import BaseModel, EmailStr

router = APIRouter()

user_repository = UserRepository()
auth_service = AuthService(user_repository)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, response: Response) -> RegisterResponse:
    """
    Handle user registration.
    """
    register_response = auth_service.register(request=request)
    
    # Set Cookies
    set_auth_cookies(response, register_response.user_id)
    
    return register_response

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """
    Handle user login with email and password.
    """
    user = auth_service.login(email=request.email, password=request.password)
    
    # Set Cookies
    set_auth_cookies(response, str(user.id))
    
    # Return user info (excluding sensitive data)
    return {
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "handle": user.handle,
        "bio": user.bio,
    }

@router.post("/logout")
async def logout(response: Response):
    """
    Clear authentication cookies.
    """
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/v1/auth/refresh")
    # Also delete potentially global refresh token if we messed up pathing previously
    response.delete_cookie("refresh_token") 
    return {"message": "Logged out successfully"}

@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    """
    Refresh access token using refresh token cookie.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
        
    try:
        payload = TokenService.decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
            
        user_id = payload.get("sub")
        if not user_id:
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
             
        # Rotate tokens (create new ones)
        set_auth_cookies(response, user_id)
        
        return {"message": "Token refreshed"}
        
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    auth_service.forgot_password(request.email)
    return {"message": "If the email exists, a reset code has been sent."}

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    auth_service.reset_password(request.email, request.code, request.new_password)
    return {"message": "Password reset successfully"}
