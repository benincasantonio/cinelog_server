"""create movie ratings table

Revision ID: 003_create_movie_ratings_table
Revises: 002_create_users_table
Create Date: 2026-06-01 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_create_movie_ratings_table"
down_revision: str | Sequence[str] | None = "002_create_users_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "movie_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("movies.id"), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("rating BETWEEN 1 AND 10", name="ck_movie_ratings_rating_range"),
        sa.UniqueConstraint("user_id", "tmdb_id", name="uq_movie_ratings_user_tmdb"),
    )

    op.create_index("ix_movie_ratings_user_movie", "movie_ratings", ["user_id", "movie_id"], unique=False)


def downgrade() -> None:
    """Rollback the migration."""
    op.drop_index("ix_movie_ratings_user_movie", table_name="movie_ratings")
    op.drop_table("movie_ratings")
