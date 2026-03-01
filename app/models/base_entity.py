from datetime import datetime, timezone

from beanie import Document, Insert, Replace, SaveChanges, before_event
from pydantic import ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntity(Document):
    deleted: bool = False
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)

    @before_event(Insert)
    def set_created_updated_dates(self) -> None:
        now = utc_now()
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now

    @staticmethod
    def active_filter(extra: dict | None = None) -> dict:
        """Return a filter dict that excludes soft-deleted documents."""
        filters: dict = {"deleted": {"$ne": True}}
        if extra:
            filters.update(extra)
        return filters

    @before_event([Replace, SaveChanges])
    def set_updated_date(self) -> None:
        self.updated_at = utc_now()
