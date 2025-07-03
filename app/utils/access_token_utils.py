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

    payload = {
        "sub": user_id,
        "exp": expiration
    }

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