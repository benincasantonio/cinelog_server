"""Reusable strongly typed values for cursor pagination.

Types:
    TimestampUUIDCursor — seek position ordered by a timestamp and UUID
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TimestampUUIDCursor:
    """Strongly typed seek position shared by timestamp-and-UUID pagination."""

    timestamp: datetime
    id: UUID
