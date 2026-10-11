"""Separate provider identity and observations from canonical movies.

Revision ID: 010_create_movie_providers_table
Revises: 009_drop_denormalized_columns

Stop old API instances before upgrading. Backfill includes deleted movies and
preserves payloads and observation timestamps, including NULL. Downgrade refuses
any state the old mandatory integer TMDB identity cannot represent losslessly.
The SQL guards also run when applying an offline-generated migration script.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010_create_movie_providers_table"
down_revision: str | Sequence[str] | None = "009_drop_denormalized_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Move every existing source identity/observation without changing any UUID."""
    op.create_table(
        "movie_providers",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("movies.id"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("provider", "external_id", name="pk_movie_providers"),
        sa.UniqueConstraint("movie_id", "provider", name="uq_movie_providers_movie_provider"),
        # Freeze this revision's allowlist; future providers need a new migration.
        sa.CheckConstraint("provider IN ('tmdb')", name="ck_movie_providers_provider"),
        sa.CheckConstraint("length(btrim(external_id)) > 0", name="ck_movie_providers_external_id"),
    )
    op.execute(
        """
        INSERT INTO movie_providers (provider, external_id, movie_id, payload, last_synced_at)
        SELECT 'tmdb', tmdb_id::text, id, tmdb_payload, tmdb_last_synced_at FROM movies
        """
    )
    op.drop_index("ix_movies_tmdb_id", table_name="movies")
    op.drop_column("movies", "tmdb_id")
    op.drop_column("movies", "tmdb_payload")
    op.drop_column("movies", "tmdb_last_synced_at")


def downgrade() -> None:
    """Reconstruct legacy columns only if every mapping can be preserved exactly."""
    op.execute(
        """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM movie_providers WHERE provider <> 'tmdb') THEN
        RAISE EXCEPTION 'Cannot downgrade: additional providers would be lost';
    END IF;
    IF EXISTS (
        SELECT 1 FROM movies m
        LEFT JOIN movie_providers p ON p.movie_id = m.id AND p.provider = 'tmdb'
        WHERE p.movie_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Cannot downgrade: a movie has no TMDB mapping';
    END IF;
    IF EXISTS (
        SELECT 1 FROM movie_providers
        WHERE NOT CASE
            WHEN external_id ~ '^-?[0-9]+$' AND length(external_id) <= 11
            THEN external_id::bigint BETWEEN -2147483648 AND 2147483647
            ELSE FALSE
        END
    ) THEN
        RAISE EXCEPTION 'Cannot downgrade: an external ID is not a legacy integer';
    END IF;
    IF EXISTS (
        SELECT external_id::integer FROM movie_providers
        GROUP BY external_id::integer HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot downgrade: external IDs collide after integer conversion';
    END IF;
    IF EXISTS (
        SELECT 1 FROM movie_providers WHERE external_id <> (external_id::integer)::text
    ) THEN
        RAISE EXCEPTION 'Cannot downgrade: integer conversion would change an external ID';
    END IF;
END $$
        """
    )
    op.add_column("movies", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("tmdb_payload", postgresql.JSONB(), nullable=True))
    op.add_column("movies", sa.Column("tmdb_last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE movies m SET tmdb_id = p.external_id::integer,
            tmdb_payload = p.payload, tmdb_last_synced_at = p.last_synced_at
        FROM movie_providers p WHERE p.movie_id = m.id AND p.provider = 'tmdb'
        """
    )
    op.alter_column("movies", "tmdb_id", nullable=False)
    op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)
    op.drop_table("movie_providers")
