from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_403_FORBIDDEN
from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.auth_utils import CSRF_TOKEN_COOKIE


class CSRFMiddleware:
    def __init__(self, app: ASGIApp, exempt_paths: list[str] | None = None):
        self.app = app
        self.exempt_paths = exempt_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            if request.url.path not in self.exempt_paths:
                csrf_token_header = request.headers.get("X-CSRF-Token")
                csrf_token_cookie = request.cookies.get(CSRF_TOKEN_COOKIE)

                if not csrf_token_header or not csrf_token_cookie or csrf_token_header != csrf_token_cookie:
                    response = JSONResponse(
                        status_code=HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF token mismatch or missing"}
                    )
                    await response(scope, receive, send)
                    return

        await self.app(scope, receive, send)
