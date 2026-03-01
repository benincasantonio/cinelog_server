from datetime import datetime

from beanie import PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.base_entity import BaseEntity


class User(BaseEntity):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId)
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    email: str
    handle: str
    bio: str | None = None
    date_of_birth: datetime | None = Field(default=None, alias="dateOfBirth")
    password_hash: str | None = Field(default=None, alias="passwordHash")
    reset_password_code: str | None = Field(default=None, alias="resetPasswordCode")
    reset_password_expires: datetime | None = Field(
        default=None, alias="resetPasswordExpires"
    )

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("createdAt", DESCENDING)]),
            IndexModel([("deleted", ASCENDING)]),
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("handle", ASCENDING)], unique=True),
        ]
