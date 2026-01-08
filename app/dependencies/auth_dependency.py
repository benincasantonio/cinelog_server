from fastapi import Request, HTTPException

from app.repository.firebase_auth_repository import FirebaseAuthRepository
from firebase_admin import auth


def auth_dependency(request: Request) -> bool:
    """
    Auth dependency check if the user is authenticated via Firebase ID token.
    """
    token = request.headers.get("Authorization")

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[len("Bearer ") :]

    try:
        # Verify Firebase ID token
        FirebaseAuthRepository.verify_id_token(token, check_revoked=True)
        return True
    except ValueError:
        # Firebase not initialized
        raise HTTPException(status_code=401, detail="Unauthorized")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token revoked")
    except auth.UserDisabledError:
        raise HTTPException(status_code=401, detail="User account is disabled")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
