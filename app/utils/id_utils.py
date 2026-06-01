"""ID conversion helpers for cross-database migrations."""

from uuid import NAMESPACE_URL, UUID, uuid5

from beanie import PydanticObjectId


def mongo_id_to_uuid(mongo_id: str | PydanticObjectId) -> UUID:
    """Derive a stable PostgreSQL UUID from a MongoDB ObjectId value."""
    return uuid5(NAMESPACE_URL, str(mongo_id))


def is_valid_uuid(id_str: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        UUID(id_str)
        return True
    except ValueError:
        return False
