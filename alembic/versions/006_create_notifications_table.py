"""create notifications table

Revision ID: 006_create_notifications_table
Revises: 005_rename_profile_visibility
Create Date: 2026-07-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_create_notifications_table"
down_revision: str | Sequence[str] | None = "005_rename_profile_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFICATION_TYPE_CONSTRAINT = "type IN ('follow.started', 'follow.requested', 'follow.accepted')"


def upgrade() -> None:
    """Create typed common notification persistence."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("deduplication_key", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(NOTIFICATION_TYPE_CONSTRAINT, name="ck_notifications_type"),
    )
    op.create_index(
        "ix_notifications_recipient_chronology",
        "notifications",
        ["recipient_id", sa.text("created_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("deleted IS FALSE"),
    )
    op.create_index(
        "ix_notifications_recipient_unread_chronology",
        "notifications",
        ["recipient_id", sa.text("created_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("deleted IS FALSE AND read_at IS NULL"),
    )
    op.create_index(
        "uq_notifications_active_recipient_deduplication_key",
        "notifications",
        ["recipient_id", "deduplication_key"],
        unique=True,
        postgresql_where=sa.text("deleted IS FALSE AND deduplication_key IS NOT NULL"),
    )


def downgrade() -> None:
    """Drop notification persistence."""

    op.drop_index("uq_notifications_active_recipient_deduplication_key", table_name="notifications")
    op.drop_index("ix_notifications_recipient_unread_chronology", table_name="notifications")
    op.drop_index("ix_notifications_recipient_chronology", table_name="notifications")
    op.drop_table("notifications")
