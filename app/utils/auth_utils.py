from fastapi import Response
from datetime import timedelta
import os
import secrets

from app.services.token_service import TokenService

# Cookie Configuration
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Cookie Name Constants
# __Host- prefix enforces: Secure=True, Path=/, no Domain attribute
# This prevents subdomain cookie injection attacks
ACCESS_TOKEN_COOKIE = "__Host-access_token"  # nosec B105
CSRF_TOKEN_COOKIE = "__Host-csrf_token"  # nosec B105
REFRESH_TOKEN_COOKIE = "refresh_token"  # nosec B105 — No __Host- prefix: needs path="/v1/auth/refresh"
RATE_LIMIT_SESSION_COOKIE = "__Host-session_id"  # nosec B105
RATE_LIMIT_SESSION_TTL_SECONDS = 3600 * 24 * 7


def generate_rate_limit_session_id() -> str:
    """Return a new opaque anonymous session ID for rate limiting."""
    return secrets.token_hex(16)


def set_auth_cookies(response: Response, user_id: str):
    """
    Helper to set access and refresh tokens in HttpOnly cookies.
    """
    # Create Tokens
    access_token = TokenService.create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = TokenService.create_refresh_token(
        data={"sub": user_id}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    # Set Access Token Cookie (__Host- prefix)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Set Refresh Token Cookie (path-scoped, no __Host- prefix)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/v1/auth/refresh",
    )

    return access_token, refresh_token


def set_csrf_cookie(response: Response):
    """
    Generate and set CSRF token cookie (__Host- prefix).
    """
    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=csrf_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600 * 24,  # 1 day
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    """
    Clears all authentication and CSRF cookies from the response.
    """
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE, path="/", secure=True, httponly=True, samesite="strict"
    )
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE,
        path="/v1/auth/refresh",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        CSRF_TOKEN_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
    )


def set_rate_limit_session_id(response: Response, session_id: str | None = None):
    """
    Set a unique session ID cookie for rate limiting purposes.
    This is used to track unauthenticated users for rate limiting.
    """
    if session_id is None:
        session_id = generate_rate_limit_session_id()

    response.set_cookie(
        key=RATE_LIMIT_SESSION_COOKIE,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=RATE_LIMIT_SESSION_TTL_SECONDS,
        path="/",
    )

    return session_id
