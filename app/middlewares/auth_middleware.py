from starlette.middleware.base import BaseHTTPMiddleware, Response

from app.utils.access_token_utils import is_valid_access_token


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token_header: str = "Authorization"):
        super().__init__(app)
        self.token_header = token_header


    async def dispatch(self, request, call_next):
        # Check for the presence of the token in the request headers
        token = request.headers.get(self.token_header)

        if not token:
            return Response("Unauthorized", status_code=401)

        is_valid = is_valid_access_token(token)

        if not is_valid:
            return Response("Unauthorized", status_code=401)
        
        response = await call_next(request)
        return response

