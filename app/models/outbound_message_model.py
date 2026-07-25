"""PostgreSQL outbound-message (transactional outbox) ORM model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config.outbound_message_config import MAX_FAILURE_DETAIL_LENGTH
from app.models.base_model import BaseEntity
from app.types import OutboundMessageChannel, OutboundMessageKind, OutboundMessageStatus


class OutboundMessage(BaseEntity):
    """Durable transactional-outbox row for a single channel delivery attempt stream."""

    __tablename__ = "outbound_messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    notification_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Deadline after which the payload is worthless — a verification code outlives its
    # own message otherwise, because the default backoff schedules the final attempt at
    # roughly the code's own TTL. NULL means the content does not expire.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    _kind_sql = ", ".join(f"'{kind.value}'" for kind in OutboundMessageKind)
    _channel_sql = ", ".join(f"'{channel.value}'" for channel in OutboundMessageChannel)
    _status_sql = ", ".join(f"'{status.value}'" for status in OutboundMessageStatus)

    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_kind_sql})",
            name="ck_outbound_messages_kind",
        ),
        CheckConstraint(
            f"channel IN ({_channel_sql})",
            name="ck_outbound_messages_channel",
        ),
        CheckConstraint(
            f"status IN ({_status_sql})",
            name="ck_outbound_messages_status",
        ),
        CheckConstraint(
            f"(kind = '{OutboundMessageKind.NOTIFICATION.value}') = (notification_id IS NOT NULL)",
            name="ck_outbound_messages_notification_reference",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_outbound_messages_attempt_count",
        ),
        CheckConstraint(
            f"last_error IS NULL OR char_length(last_error) <= {MAX_FAILURE_DETAIL_LENGTH}",
            name="ck_outbound_messages_last_error_length",
        ),
        UniqueConstraint(
            "notification_id",
            "channel",
            name="uq_outbound_messages_notification_channel",
        ),
        Index(
            "ix_outbound_messages_claimable",
            "channel",
            "available_at",
            "id",
            postgresql_where=text("deleted IS FALSE AND status = 'pending'"),
        ),
        Index(
            "ix_outbound_messages_stale_locks",
            "locked_at",
            postgresql_where=text("deleted IS FALSE AND status = 'processing'"),
        ),
    )
