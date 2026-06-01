"""create users table

Revision ID: 002_create_users_table
Revises: 001_create_movies_table
Create Date: 2026-06-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_create_users_table"
down_revision: str | Sequence[str] | None = "001_create_movies_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("profile_visibility", sa.Text(), nullable=False, server_default=sa.text("'private'")),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("reset_password_code", sa.Text(), nullable=True),
        sa.Column("reset_password_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "profile_visibility IN ('public', 'friends_only', 'private')",
            name="ck_users_profile_visibility",
        ),
    )

    op.create_index("uq_users_email_lower", "users", [sa.text("LOWER(email)")], unique=True)
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)


def downgrade() -> None:
    """Rollback the migration."""
    op.drop_index("ix_users_handle", table_name="users")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
