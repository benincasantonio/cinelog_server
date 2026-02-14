from fastapi import Request, HTTPException
from app.services.token_service import TokenService


def auth_dependency(request: Request) -> str:
    """
    Auth dependency check if the user is authenticated via local JWT cookie.
    Returns the user_id (sub) from the token.
    """
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = TokenService.decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
            
        user_id = payload.get("sub")
        if not user_id:
             raise HTTPException(status_code=401, detail="Invalid token payload")
             
        # TODO: Add CSRF check here if needed (e.g. verify X-CSRF-Token matches cookie)
        
        return user_id
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
