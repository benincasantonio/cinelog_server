"""rename friends-only profile visibility to followers-only

Revision ID: 005_rename_profile_visibility
Revises: 004_create_logs_table
Create Date: 2026-07-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005_rename_profile_visibility"
down_revision: str | Sequence[str] | None = "004_create_logs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_users_profile_visibility"
OLD_CONSTRAINT = "profile_visibility IN ('public', 'friends_only', 'private')"
NEW_CONSTRAINT = "profile_visibility IN ('public', 'followers_only', 'private')"


def upgrade() -> None:
    """Replace the legacy friends-only value with followers-only."""
    op.drop_constraint(CONSTRAINT_NAME, "users", type_="check")
    op.execute("UPDATE users SET profile_visibility = 'followers_only' WHERE profile_visibility = 'friends_only'")
    op.create_check_constraint(CONSTRAINT_NAME, "users", NEW_CONSTRAINT)


def downgrade() -> None:
    """Restore the legacy friends-only value and constraint."""
    op.drop_constraint(CONSTRAINT_NAME, "users", type_="check")
    op.execute("UPDATE users SET profile_visibility = 'friends_only' WHERE profile_visibility = 'followers_only'")
    op.create_check_constraint(CONSTRAINT_NAME, "users", OLD_CONSTRAINT)
