"""Index retained follow notification history for the rolling cooldown.

Revision ID: 011_add_follow_cooldown_index
Revises: 010_create_movie_providers_table
"""

import sqlalchemy as sa

from alembic import op

revision = "011_add_follow_cooldown_index"
down_revision = "010_create_movie_providers_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_follow_started_cooldown",
        "notifications",
        ["recipient_id", "actor_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("type = 'follow.started'"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_follow_started_cooldown", table_name="notifications")
