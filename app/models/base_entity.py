from mongoengine import Document, DateTimeField, BooleanField
from datetime import datetime, timezone


class BaseEntity(Document):
    """
    Abstract base class that provides common fields for all entity models
    """

    meta = {
        "abstract": True,
        "indexes": [
            "-created_at",
            "deleted",
        ],
    }

    deleted = BooleanField(default=False)
    deleted_at = DateTimeField(db_field="deletedAt")
    created_at = DateTimeField(
        db_field="createdAt", default=lambda: datetime.now(timezone.utc)
    )
    updated_at = DateTimeField(
        db_field="updatedAt", default=lambda: datetime.now(timezone.utc)
    )

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)
