from beanie import PydanticObjectId
from bson.errors import InvalidId


def to_object_id(value: str | PydanticObjectId | None) -> PydanticObjectId | None:
    if value is None:
        return None
    if isinstance(value, PydanticObjectId):
        return value
    try:
        return PydanticObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None
