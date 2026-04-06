"""
Rate limiting utilities.

Provides a custom exception handler for slowapi's RateLimitExceeded that
returns a structured ErrorSchema response consistent with the rest of the API,
while preserving the Retry-After and X-RateLimit-* headers injected by slowapi.
"""

from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address

from app.utils.error_codes import ErrorCodes

RATE_LIMIT_SESSION_STATE = "rate_limit_session_id"


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a structured 429 response matching the API's ErrorSchema format."""
    error = ErrorCodes.RATE_LIMIT_EXCEEDED
    response = JSONResponse(
        status_code=error.error_code,
        content={
            "error_code_name": error.error_code_name,
            "error_code": error.error_code,
            "error_message": error.error_message,
            "error_description": error.error_description,
        },
    )
    response = cast(
        JSONResponse,
        request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        ),
    )
    return response


def get_rate_limit_key(request: Request) -> str:
    """Prefer authenticated user, then fall back to the client IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return f"user:{user_id}"

    return get_ip_rate_limit_key(request)


def get_ip_rate_limit_key(request: Request) -> str:
    """Return the client IP key for coarse outer rate limits."""
    return f"ip:{get_remote_address(request)}"


def get_session_rate_limit_key(request: Request) -> str:
    """Return the validated anonymous session key for session-scoped limits."""
    session_id = getattr(request.state, RATE_LIMIT_SESSION_STATE, None)
    if session_id:
        return f"session:{session_id}"

    return get_ip_rate_limit_key(request)
