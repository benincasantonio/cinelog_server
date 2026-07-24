"""PostgreSQL notification ORM model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseEntity
from app.models.user_model import User
from app.types import NotificationType


class Notification(BaseEntity):
    """Persisted common notification presentation and read state."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    recipient_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    deduplication_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id], lazy="raise")

    _notification_type_sql = ", ".join(f"'{notification_type.value}'" for notification_type in NotificationType)

    __table_args__ = (
        CheckConstraint(
            f"type IN ({_notification_type_sql})",
            name="ck_notifications_type",
        ),
        Index(
            "ix_notifications_recipient_chronology",
            "recipient_id",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("deleted IS FALSE"),
        ),
        Index(
            "ix_notifications_recipient_unread_chronology",
            "recipient_id",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_where=text("deleted IS FALSE AND read_at IS NULL"),
        ),
        Index(
            "uq_notifications_active_recipient_deduplication_key",
            "recipient_id",
            "deduplication_key",
            unique=True,
            postgresql_where=text("deleted IS FALSE AND deduplication_key IS NOT NULL"),
        ),
    )
