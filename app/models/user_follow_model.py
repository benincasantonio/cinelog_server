"""PostgreSQL model for accepted directional user follows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class UserFollow(Base):
    """An accepted, directional follower-to-followed relationship."""

    __tablename__ = "user_follows"

    follower_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    followed_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("follower_id <> followed_id", name="ck_user_follows_not_self"),
        Index("ix_user_follows_followed_id", "followed_id"),
    )
