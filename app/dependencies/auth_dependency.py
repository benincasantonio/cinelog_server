from uuid import UUID

from beanie import PydanticObjectId
from fastapi import HTTPException, Request

from app.services.token_service import TokenService
from app.utils.auth_utils import ACCESS_TOKEN_COOKIE
from app.utils.id_utils import is_valid_uuid


def auth_dependency(request: Request) -> PydanticObjectId | UUID:
    """
    Auth dependency check if the user is authenticated via local JWT cookie.
    Returns the user_id (sub) from the token.
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = TokenService.decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        request.state.user_id = user_id

        print(f"Authenticated user_id: {user_id} from token in auth_dependency")

        if is_valid_uuid(user_id):
            return UUID(user_id)

        return PydanticObjectId(user_id)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized") from None
