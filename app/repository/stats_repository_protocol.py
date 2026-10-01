from datetime import date
from typing import Protocol
from uuid import UUID

from app.schemas.stats_schemas import UserStatsAggregate


class StatsRepositoryProtocol(Protocol):
    """Protocol for the cross-table user statistics read model."""

    async def get_user_stats(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> UserStatsAggregate:
        """Compute aggregate viewing statistics for a user."""
