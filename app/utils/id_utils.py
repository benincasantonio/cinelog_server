"""ID validation helpers."""

from uuid import UUID


def is_valid_uuid(id_str: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        UUID(id_str)
        return True
    except ValueError:
        return False
