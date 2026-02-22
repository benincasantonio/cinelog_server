from fastapi import APIRouter, Response, status, HTTPException, Request
import jwt

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    CsrfTokenResponse,
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService
from app.utils.auth_utils import (
    set_auth_cookies,
    set_csrf_cookie,
    ACCESS_TOKEN_COOKIE,
    CSRF_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
)

router = APIRouter()

user_repository = UserRepository()
auth_service = AuthService(user_repository)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(request: RegisterRequest) -> RegisterResponse:
    """
    Handle user registration.
    User must login separately after registration.
    """
    return auth_service.register(request=request)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response) -> LoginResponse:
    """
    Handle user login with email and password.
    """
    user = auth_service.login(email=request.email, password=request.password)

    # Set Cookies
    set_auth_cookies(response, str(user.id))
    csrf_token = set_csrf_cookie(response)

    return LoginResponse(
        user_id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        handle=user.handle,
        bio=user.bio,
        csrf_token=csrf_token,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(response: Response) -> LogoutResponse:
    """
    Clear authentication cookies.
    """
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/v1/auth/refresh")
    response.delete_cookie(CSRF_TOKEN_COOKIE, path="/")
    return LogoutResponse(message="Logged out successfully")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: Request, response: Response) -> RefreshResponse:
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
        csrf_token = set_csrf_cookie(response)

        return RefreshResponse(message="Token refreshed", csrf_token=csrf_token)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except HTTPException:
        raise


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(request: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """
    Initiate password recovery. Sends reset code via email.
    """
    auth_service.forgot_password(request.email)
    return ForgotPasswordResponse(message="If the email exists, a reset code has been sent.")


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(request: ResetPasswordRequest) -> ResetPasswordResponse:
    """
    Complete password recovery with reset code.
    """
    auth_service.reset_password(request.email, request.code, request.new_password)
    return ResetPasswordResponse(message="Password reset successfully")


@router.get("/csrf", response_model=CsrfTokenResponse)
async def get_csrf_token(response: Response) -> CsrfTokenResponse:
    """
    Get CSRF token (sets HttpOnly cookie and returns token in body).
    """
    csrf_token = set_csrf_cookie(response)
    return CsrfTokenResponse(csrf_token=csrf_token)
