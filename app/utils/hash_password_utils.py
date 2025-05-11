from bcrypt import hashpw, gensalt, checkpw

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt securely.
    
    Args:
        password (str): The password to hash.
    
    Returns:
        str: The hashed password.
    """

    hashed = hashpw(password.encode('utf-8'), gensalt())
    
    return hashed.decode('utf-8')

def check_password(password: str, hashed_password: str) -> bool:
    """
    Check a password against a hashed password using bcrypt.
    
    Args:
        password (str): The password to check.
        hashed_password (str): The hashed password to check against.
    
    Returns:
        bool: True if the password matches the hashed password, False otherwise.
    """

    return checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))