"""create movies table

Revision ID: 001_create_movies_table
Revises:
Create Date: 2026-05-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_create_movies_table"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "movies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("release_date", sa.DateTime(timezone=False), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column("vote_average", sa.Float(), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("original_language", sa.Text(), nullable=True),
        sa.Column("tmdb_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tmdb_last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)


def downgrade() -> None:
    """Rollback the migration."""
    op.drop_index("ix_movies_tmdb_id", table_name="movies")
    op.drop_table("movies")
