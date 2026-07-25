"""create outbound_messages table

The revision id is intentionally shorter than the "create outbound_messages_table"
filename convention would suggest: Alembic's default ``alembic_version.version_num``
column is ``VARCHAR(32)``, and ``007_create_outbound_messages_table`` (34 characters)
does not fit — it silently truncates and raises ``StringDataRightTruncationError``
on upgrade. ``007_create_outbound_messages`` fits comfortably under the limit.

Revision ID: 007_create_outbound_messages
Revises: 006_create_notifications_table
Create Date: 2026-07-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007_create_outbound_messages"
down_revision: str | Sequence[str] | None = "006_create_notifications_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OUTBOUND_MESSAGE_KIND_CONSTRAINT = (
    "kind IN ('notification', 'registration_verification', 'registration_existing_account', 'password_reset')"
)
OUTBOUND_MESSAGE_CHANNEL_CONSTRAINT = "channel IN ('email')"
OUTBOUND_MESSAGE_STATUS_CONSTRAINT = "status IN ('pending', 'processing', 'delivered', 'failed')"
OUTBOUND_MESSAGE_NOTIFICATION_REFERENCE_CONSTRAINT = "(kind = 'notification') = (notification_id IS NOT NULL)"
OUTBOUND_MESSAGE_ATTEMPT_COUNT_CONSTRAINT = "attempt_count >= 0"
OUTBOUND_MESSAGE_LAST_ERROR_LENGTH_CONSTRAINT = "last_error IS NULL OR char_length(last_error) <= 500"


def upgrade() -> None:
    """Create the durable transactional-outbox table for outbound message delivery."""

    op.create_table(
        "outbound_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(OUTBOUND_MESSAGE_KIND_CONSTRAINT, name="ck_outbound_messages_kind"),
        sa.CheckConstraint(OUTBOUND_MESSAGE_CHANNEL_CONSTRAINT, name="ck_outbound_messages_channel"),
        sa.CheckConstraint(OUTBOUND_MESSAGE_STATUS_CONSTRAINT, name="ck_outbound_messages_status"),
        sa.CheckConstraint(
            OUTBOUND_MESSAGE_NOTIFICATION_REFERENCE_CONSTRAINT,
            name="ck_outbound_messages_notification_reference",
        ),
        sa.CheckConstraint(OUTBOUND_MESSAGE_ATTEMPT_COUNT_CONSTRAINT, name="ck_outbound_messages_attempt_count"),
        sa.CheckConstraint(
            OUTBOUND_MESSAGE_LAST_ERROR_LENGTH_CONSTRAINT,
            name="ck_outbound_messages_last_error_length",
        ),
        sa.UniqueConstraint("notification_id", "channel", name="uq_outbound_messages_notification_channel"),
    )
    op.create_index(
        "ix_outbound_messages_claimable",
        "outbound_messages",
        ["channel", "available_at", "id"],
        postgresql_where=sa.text("deleted IS FALSE AND status = 'pending'"),
    )
    op.create_index(
        "ix_outbound_messages_stale_locks",
        "outbound_messages",
        ["locked_at"],
        postgresql_where=sa.text("deleted IS FALSE AND status = 'processing'"),
    )


def downgrade() -> None:
    """Drop the transactional-outbox table."""

    op.drop_index("ix_outbound_messages_stale_locks", table_name="outbound_messages")
    op.drop_index("ix_outbound_messages_claimable", table_name="outbound_messages")
    op.drop_table("outbound_messages")
