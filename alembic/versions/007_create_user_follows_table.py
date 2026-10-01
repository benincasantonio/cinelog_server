"""create user_follows table

Revision ID: 007_create_user_follows_table
Revises: 006_create_notifications_table
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007_create_user_follows_table"
down_revision: str | Sequence[str] | None = "006_create_notifications_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create accepted directional user-follow persistence."""

    op.create_table(
        "user_follows",
        sa.Column(
            "follower_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "followed_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("follower_id <> followed_id", name="ck_user_follows_not_self"),
    )
    op.create_index("ix_user_follows_followed_id", "user_follows", ["followed_id"])


def downgrade() -> None:
    """Drop accepted directional user-follow persistence."""

    op.drop_index("ix_user_follows_followed_id", table_name="user_follows")
    op.drop_table("user_follows")
