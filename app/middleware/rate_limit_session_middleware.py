"""Validate and issue anonymous rate-limit session cookies on public auth routes."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config.public_routes import PUBLIC_AUTH_PATHS
from app.services.rate_limit_cache_service import RateLimitCacheService
from app.utils.auth_utils import (
    RATE_LIMIT_SESSION_COOKIE,
    generate_rate_limit_session_id,
    set_rate_limit_session_id,
)
from app.utils.rate_limit_utils import RATE_LIMIT_SESSION_STATE


class RateLimitSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._rate_limit_cache = RateLimitCacheService()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path not in PUBLIC_AUTH_PATHS:
            return await call_next(request)

        session_id = request.cookies.get(RATE_LIMIT_SESSION_COOKIE)
        has_valid_session = False
        issued_session_id: str | None = None

        if session_id:
            session_data = await self._rate_limit_cache.get_session(session_id)
            if session_data is not None:
                setattr(request.state, RATE_LIMIT_SESSION_STATE, session_id)
                await self._rate_limit_cache.upsert_session(session_id)
                has_valid_session = True

        if not has_valid_session:
            issued_session_id = generate_rate_limit_session_id()
            setattr(request.state, RATE_LIMIT_SESSION_STATE, issued_session_id)
            await self._rate_limit_cache.upsert_session(issued_session_id)

        response = await call_next(request)

        if issued_session_id is not None:
            set_rate_limit_session_id(response, issued_session_id)

        return response
