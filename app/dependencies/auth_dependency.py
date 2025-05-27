from fastapi import Request, HTTPException

from app.utils.access_token_utils import is_valid_access_token


def auth_dependency(request: Request) -> bool:
    """
    Auth dependency check if the user is authenticated.
    """
    token = request.headers.get("Authorization")

    if not token or not is_valid_access_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return True

