from fastapi import APIRouter, Response, status, Request
from fastapi.responses import JSONResponse
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
    clear_auth_cookies,
)

router = APIRouter()

user_repository = UserRepository()
auth_service = AuthService(user_repository)


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse
)
async def register(request: RegisterRequest) -> RegisterResponse:
    """
    Handle user registration.
    User must login separately after registration.
    """
    return await auth_service.register(request=request)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response) -> LoginResponse:
    """
    Handle user login with email and password.
    """
    user = await auth_service.login(email=request.email, password=request.password)

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
    clear_auth_cookies(response)
    return LogoutResponse(message="Logged out successfully")


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={401: {"description": "Invalid, expired, or missing refresh token"}},
)
async def refresh_token(
    request: Request, response: Response
) -> RefreshResponse | JSONResponse:
    """
    Refresh access token using refresh token cookie.
    """

    def clear_cookies_response(detail: str) -> JSONResponse:
        err_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": detail}
        )
        clear_auth_cookies(err_response)
        return err_response

    token = request.cookies.get("refresh_token")
    if not token:
        return clear_cookies_response("Refresh token missing")

    try:
        payload = TokenService.decode_token(token)
        if payload.get("type") != "refresh":
            return clear_cookies_response("Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            return clear_cookies_response("Invalid token payload")

        # Rotate tokens (create new ones)
        set_auth_cookies(response, user_id)
        csrf_token = set_csrf_cookie(response)

        return RefreshResponse(message="Token refreshed", csrf_token=csrf_token)

    except jwt.ExpiredSignatureError:
        return clear_cookies_response("Refresh token expired")
    except jwt.InvalidTokenError:
        return clear_cookies_response("Invalid refresh token")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(request: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """
    Initiate password recovery. Sends reset code via email.
    """
    await auth_service.forgot_password(request.email)
    return ForgotPasswordResponse(
        message="If the email exists, a reset code has been sent."
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(request: ResetPasswordRequest) -> ResetPasswordResponse:
    """
    Complete password recovery with reset code.
    """
    await auth_service.reset_password(request.email, request.code, request.new_password)
    return ResetPasswordResponse(message="Password reset successfully")


@router.get("/csrf", response_model=CsrfTokenResponse)
async def get_csrf_token(response: Response) -> CsrfTokenResponse:
    """
    Get CSRF token (sets HttpOnly cookie and returns token in body).
    """
    csrf_token = set_csrf_cookie(response)
    return CsrfTokenResponse(csrf_token=csrf_token)
