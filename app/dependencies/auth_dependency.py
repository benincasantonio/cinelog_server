from fastapi import Request, HTTPException
from app.services.token_service import TokenService


def auth_dependency(request: Request) -> str:
    """
    Auth dependency check if the user is authenticated via local JWT cookie.
    Returns the user_id (sub) from the token.
    """
    token = request.cookies.get("access_token")

    if not token:
        # Fallback to Authorization header for flexibility (optional but good for testing/portability)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
             token = auth_header[len("Bearer ") :]
    
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
        
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
