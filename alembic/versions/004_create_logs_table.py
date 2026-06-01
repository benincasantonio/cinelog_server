"""create logs table

Revision ID: 004_create_logs_table
Revises: 003_create_movie_ratings_table
Create Date: 2026-06-01 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_create_logs_table"
down_revision: str | Sequence[str] | None = "003_create_movie_ratings_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("movies.id"), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("date_watched", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewing_notes", sa.Text(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column("watched_where", sa.Text(), nullable=False, server_default=sa.text("'other'")),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "watched_where IN ('cinema', 'streaming', 'homeVideo', 'tv', 'other')",
            name="ck_logs_watched_where",
        ),
    )

    op.execute("CREATE INDEX ix_logs_user_date_watched ON logs (user_id, date_watched DESC)")
    op.execute(
        "CREATE INDEX ix_logs_user_date_watched_created_at ON logs (user_id, date_watched DESC, created_at DESC)"
    )
    op.execute("CREATE INDEX ix_logs_user_movie ON logs (user_id, movie_id)")
    op.execute("CREATE INDEX ix_logs_tmdb_date_watched ON logs (tmdb_id, date_watched DESC)")
    op.execute("CREATE INDEX ix_logs_user_watched_where_created_at ON logs (user_id, watched_where, created_at)")


def downgrade() -> None:
    """Rollback the migration."""
    op.drop_index("ix_logs_user_watched_where_created_at", table_name="logs")
    op.drop_index("ix_logs_tmdb_date_watched", table_name="logs")
    op.drop_index("ix_logs_user_movie", table_name="logs")
    op.drop_index("ix_logs_user_date_watched_created_at", table_name="logs")
    op.drop_index("ix_logs_user_date_watched", table_name="logs")
    op.drop_table("logs")
