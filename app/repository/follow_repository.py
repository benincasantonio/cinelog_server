"""PostgreSQL repository for accepted directional user follows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from app.models.user_follow_model import UserFollow
from app.models.user_model import User
from app.repository.follow_repository_protocol import FollowSummary
from app.repository.repository_base import RepositoryBase


class FollowRepository(RepositoryBase):
    """Persist and aggregate accepted user-follow edges."""

    async def create_follow(self, follower_id: UUID, followed_id: UUID) -> None:
        """Idempotently insert a follow edge using its composite primary key."""

        async with self._session_provider() as session:
            statement = (
                insert(UserFollow)
                .values(follower_id=follower_id, followed_id=followed_id)
                .on_conflict_do_nothing(index_elements=[UserFollow.follower_id, UserFollow.followed_id])
            )
            await session.execute(statement)
            await session.commit()

    async def delete_follow(self, follower_id: UUID, followed_id: UUID) -> None:
        """Idempotently delete a follow edge."""

        async with self._session_provider() as session:
            statement = delete(UserFollow).where(
                UserFollow.follower_id == follower_id,
                UserFollow.followed_id == followed_id,
            )
            await session.execute(statement)
            await session.commit()

    async def is_following(self, follower_id: UUID, followed_id: UUID) -> bool:
        """Return whether an edge connects two active users."""

        follower = aliased(User)
        followed = aliased(User)
        async with self._session_provider() as session:
            statement = (
                select(UserFollow.follower_id)
                .join(follower, follower.id == UserFollow.follower_id)
                .join(followed, followed.id == UserFollow.followed_id)
                .where(
                    UserFollow.follower_id == follower_id,
                    UserFollow.followed_id == followed_id,
                    follower.active(),
                    followed.active(),
                )
                .limit(1)
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none() is not None

    async def get_follow_summary(self, user_id: UUID, requester_id: UUID) -> FollowSummary:
        """Aggregate active edges for a profile in one database round trip."""

        active_follower = aliased(User)
        active_followed = aliased(User)
        active_requester = aliased(User)

        follower_count = (
            select(func.count())
            .select_from(UserFollow)
            .join(active_follower, active_follower.id == UserFollow.follower_id)
            .where(
                UserFollow.followed_id == user_id,
                active_follower.active(),
            )
            .scalar_subquery()
        )
        following_count = (
            select(func.count())
            .select_from(UserFollow)
            .join(active_followed, active_followed.id == UserFollow.followed_id)
            .where(
                UserFollow.follower_id == user_id,
                active_followed.active(),
            )
            .scalar_subquery()
        )
        requester_follows = (
            select(UserFollow.follower_id)
            .join(active_requester, active_requester.id == UserFollow.follower_id)
            .where(
                UserFollow.follower_id == requester_id,
                UserFollow.followed_id == user_id,
                active_requester.active(),
            )
            .exists()
        )

        async with self._session_provider() as session:
            statement = select(
                follower_count.label("follower_count"),
                following_count.label("following_count"),
                requester_follows.label("is_following"),
            )
            row = (await session.execute(statement)).one()
            return FollowSummary(
                follower_count=row.follower_count,
                following_count=row.following_count,
                is_following=bool(row.is_following),
            )
