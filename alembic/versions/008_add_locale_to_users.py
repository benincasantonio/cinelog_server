"""add locale to users

Revision ID: 008_add_locale_to_users
Revises: 007_create_user_follows_table
Create Date: 2026-07-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_add_locale_to_users"
down_revision: str | Sequence[str] | None = "007_create_user_follows_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the required user locale with a deterministic existing-user backfill."""

    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.Text(),
            nullable=True,
            server_default=sa.text("'en-US'"),
        ),
    )
    op.execute("UPDATE users SET locale = 'en-US' WHERE locale IS NULL")
    op.alter_column("users", "locale", nullable=False)
    op.create_check_constraint(
        "ck_users_locale",
        "users",
        "locale IN ('en-US', 'fr-FR', 'it-IT')",
    )


def downgrade() -> None:
    """Remove the user locale."""

    op.drop_constraint("ck_users_locale", "users", type_="check")
    op.drop_column("users", "locale")
