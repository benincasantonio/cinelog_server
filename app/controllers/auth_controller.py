import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Response, status, Request, Depends
from fastapi.responses import JSONResponse
import jwt

from app.config.rate_limiter import limiter
from app.dependencies.auth_dependency import auth_dependency
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
from app.services.auth_rate_limit_service import (
    AuthRateLimitService,
)
from app.services.token_service import TokenService
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException
from app.utils.rate_limit_utils import (
    get_ip_rate_limit_key,
    get_session_rate_limit_key,
)
from app.utils.auth_utils import (
    set_auth_cookies,
    set_csrf_cookie,
    clear_auth_cookies,
)

router = APIRouter()
logger = logging.getLogger(__name__)

user_repository = UserRepository()
auth_service = AuthService(user_repository)
auth_rate_limit_service = AuthRateLimitService()


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse
)
@limiter.limit("10/hour", key_func=get_ip_rate_limit_key)
@limiter.limit("5/hour", key_func=get_session_rate_limit_key)
async def register(
    request: Request, response: Response, request_body: RegisterRequest
) -> RegisterResponse:
    """
    Handle user registration.
    User must login separately after registration.
    """
    return await auth_service.register(request=request_body)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("30/15minute", key_func=get_ip_rate_limit_key)
@limiter.limit("10/15minute", key_func=get_session_rate_limit_key)
async def login(
    request: Request,
    response: Response,
    request_body: LoginRequest,
) -> LoginResponse:
    """
    Handle user login with email and password.
    """
    auth_rate_limit_service.enforce_login_failure_limit(request_body.email)

    try:
        user = await auth_service.login(
            email=request_body.email, password=request_body.password
        )
    except AppException as exc:
        if exc.error == ErrorCodes.INVALID_CREDENTIALS:
            auth_rate_limit_service.register_login_failure(request_body.email)
        raise

    # Set Cookies
    set_auth_cookies(response, str(user.id))
    try:
        auth_rate_limit_service.clear_login_failures(request_body.email)
    except Exception:
        logger.warning(
            "Failed to clear login failure bucket after successful auth",
            exc_info=True,
        )
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
@limiter.limit("6/hour", key_func=get_ip_rate_limit_key)
@limiter.limit("3/hour", key_func=get_session_rate_limit_key)
async def forgot_password(
    request: Request,
    response: Response,
    request_body: ForgotPasswordRequest,
) -> ForgotPasswordResponse:
    """
    Initiate password recovery. Sends reset code via email.
    """
    auth_rate_limit_service.enforce_forgot_password_limit(request_body.email)
    # This bucket is intentionally charged before the service call so repeated
    # requests for a known email cannot bypass the per-account forgot-password
    # cap. The trade-off is a small denial-of-service window for that address
    # (5/30minute) if an attacker spends the bucket first.
    auth_rate_limit_service.register_forgot_password_attempt(request_body.email)

    await auth_service.forgot_password(request_body.email)
    return ForgotPasswordResponse(
        message="If the email exists, a reset code has been sent."
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit("10/hour", key_func=get_ip_rate_limit_key)
@limiter.limit("10/hour", key_func=get_session_rate_limit_key)
async def reset_password(
    request: Request,
    response: Response,
    request_body: ResetPasswordRequest,
) -> ResetPasswordResponse:
    """
    Complete password recovery with reset code.
    """
    auth_rate_limit_service.enforce_reset_password_limit(request_body.email)

    try:
        await auth_service.reset_password(
            request_body.email,
            request_body.code,
            request_body.new_password,
        )
    except AppException as exc:
        if exc.error == ErrorCodes.INVALID_CREDENTIALS:
            auth_rate_limit_service.register_reset_password_attempt(request_body.email)
        raise
    return ResetPasswordResponse(message="Password reset successfully")


@router.get("/csrf", response_model=CsrfTokenResponse)
@limiter.limit("300/30minute")
async def get_csrf_token(
    request: Request,
    response: Response,
    _: PydanticObjectId = Depends(auth_dependency),
) -> CsrfTokenResponse:
    """
    Get CSRF token (sets HttpOnly cookie and returns token in body).
    """
    csrf_token = set_csrf_cookie(response)
    return CsrfTokenResponse(csrf_token=csrf_token)
