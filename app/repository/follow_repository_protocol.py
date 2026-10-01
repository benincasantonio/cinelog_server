"""Protocol and read result for user-follow persistence."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class FollowSummary:
    """Counts and requester-relative state for one active profile."""

    follower_count: int
    following_count: int
    is_following: bool


class FollowRepositoryProtocol(Protocol):
    """Persistence operations for accepted directional follows."""

    async def create_follow(self, follower_id: UUID, followed_id: UUID) -> None:
        """Idempotently create a follower-to-followed edge."""

    async def delete_follow(self, follower_id: UUID, followed_id: UUID) -> None:
        """Idempotently delete a follower-to-followed edge."""

    async def is_following(self, follower_id: UUID, followed_id: UUID) -> bool:
        """Return whether both active users have the requested edge."""

    async def get_follow_summary(self, user_id: UUID, requester_id: UUID) -> FollowSummary:
        """Return active follower/following counts and requester-relative state."""
