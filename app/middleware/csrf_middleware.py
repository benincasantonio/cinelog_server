from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_403_FORBIDDEN

from app.utils.auth_utils import CSRF_TOKEN_COOKIE

class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_paths: list[str] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or []

    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            if request.url.path not in self.exempt_paths:
                csrf_token_header = request.headers.get("X-CSRF-Token")
                csrf_token_cookie = request.cookies.get(CSRF_TOKEN_COOKIE)

                if not csrf_token_header or not csrf_token_cookie or csrf_token_header != csrf_token_cookie:
                    return JSONResponse(
                        status_code=HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF token mismatch or missing"}
                    )

        response = await call_next(request)
        return response
