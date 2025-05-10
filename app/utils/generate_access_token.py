import os
import jwt
from datetime import datetime, timedelta

def generate_access_token(user_id: str) -> str:
    """
    Generate a JWT access token for the given user ID.

    Args:
        user_id (str): The ID of the user for whom to generate the token.

    Returns:
        str: The generated JWT access token.
    """

    # Define the secret key and algorithm
    SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    ALGORITHM = "HS256"

    expiration = datetime.utcnow() + timedelta(hours=1)

    payload = {
        "sub": user_id,
        "exp": expiration
    }

    # Generate the JWT token
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return token