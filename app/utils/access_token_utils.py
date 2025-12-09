import os
import jwt
from datetime import datetime, timedelta, UTC


def generate_access_token(user_id: str) -> str:
    """
    Generate a JWT access token for the given user ID.

    Args:
        user_id (str): The ID of the user for whom to generate the token.

    Returns:
        str: The generated JWT access token.
    """

    # Define the secret key and algorithm
    secret_key = os.getenv("JWT_SECRET_KEY")
    algorithm = "HS256"

    expiration = datetime.now(UTC) + timedelta(hours=1)

    payload = {"sub": user_id, "exp": expiration}

    # Generate the JWT token
    token = jwt.encode(payload, secret_key, algorithm=algorithm)

    return token


def is_valid_access_token(token: str) -> bool:
    """
    Validate the JWT access token.

    Args:
        token (str): The JWT access token to validate.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    secret_key = os.getenv("JWT_SECRET_KEY")
    algorithm = "HS256"

    if not secret_key:
        raise ValueError("JWT_SECRET_KEY environment variable is not set.")

    try:
        jwt.decode(token, secret_key, algorithms=[algorithm])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


def get_user_id_from_token(token: str) -> str:
    """
    Extract MongoDB user ID from Firebase ID token.

    Args:
        token (str): The Firebase ID token (can include "Bearer " prefix).

    Returns:
        str: The MongoDB user ID found by Firebase UID.

    Raises:
        ValueError: If token is invalid, expired, or user not found.
    """
    if not token:
        raise ValueError("No token provided")

    if token.startswith("Bearer "):
        token = token[7:]

    # Import here to avoid circular dependencies
    from app.repository.firebase_auth_repository import FirebaseAuthRepository
    from app.repository.user_repository import UserRepository
    from firebase_admin import auth

    try:
        # Verify Firebase ID token
        decoded_token = FirebaseAuthRepository.verify_id_token(token, check_revoked=True)
        firebase_uid = decoded_token.get("uid")

        if not firebase_uid:
            raise ValueError("Token does not contain Firebase UID")

        # Look up user in MongoDB by Firebase UID
        user = UserRepository.find_user_by_firebase_uid(firebase_uid)
        if not user:
            raise ValueError("User not found")

        return user.id.__str__()
    except ValueError:
        raise
    except auth.InvalidIdTokenError:
        raise ValueError("Invalid token")
    except auth.ExpiredIdTokenError:
        raise ValueError("Token has expired")
    except auth.RevokedIdTokenError:
        raise ValueError("Token has been revoked")
    except auth.UserDisabledError:
        raise ValueError("User account is disabled")
    except Exception as e:
        raise ValueError(f"Token validation failed: {str(e)}")
