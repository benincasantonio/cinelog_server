"""
Utility functions for extracting user information from Firebase ID tokens.
"""


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
    # Note: Order matters! Subclass exceptions must be caught before parent class
    except auth.ExpiredIdTokenError:
        raise ValueError("Token has expired")
    except auth.RevokedIdTokenError:
        raise ValueError("Token has been revoked")
    except auth.UserDisabledError:
        raise ValueError("User account is disabled")
    except auth.InvalidIdTokenError:
        raise ValueError("Invalid token")
    except Exception as e:
        raise ValueError(f"Token validation failed: {str(e)}")
