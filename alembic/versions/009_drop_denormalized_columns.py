"""drop denormalized movie columns

Revision ID: 009_drop_denormalized_columns
Revises: 008_add_locale_to_users
Create Date: 2026-10-10 00:00:00.000000

Removes the MongoDB-era copies of movie data from ``logs`` and ``movie_ratings``:
``logs.tmdb_id``, ``logs.poster_path`` and ``movie_ratings.tmdb_id``. ``movies`` becomes
the only source of the TMDB identity and poster. Rating uniqueness moves from
``(user_id, tmdb_id)`` to ``(user_id, movie_id)``.

The upgrade runs a pre-flight audit and refuses to drop anything when a copy
disagrees with its movie or a user has more than one rating for the same movie.

The downgrade restores the columns by backfilling them from ``movies``. Posters that
clients stored on logs, and that differ from the movie poster, cannot be restored.
"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "009_drop_denormalized_columns"
down_revision: str | Sequence[str] | None = "008_add_locale_to_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

AUDIT_SAMPLE_SIZE = 10

AUDIT_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "logs.tmdb_id disagrees with movies.tmdb_id",
        """
        SELECT l.id::text
        FROM logs l
        JOIN movies m ON m.id = l.movie_id
        WHERE l.tmdb_id <> m.tmdb_id
        ORDER BY l.id
        """,
    ),
    (
        "movie_ratings.tmdb_id disagrees with movies.tmdb_id",
        """
        SELECT r.id::text
        FROM movie_ratings r
        JOIN movies m ON m.id = r.movie_id
        WHERE r.tmdb_id <> m.tmdb_id
        ORDER BY r.id
        """,
    ),
    (
        "more than one movie_ratings row per (user_id, movie_id)",
        """
        SELECT user_id::text || '/' || movie_id::text
        FROM movie_ratings
        GROUP BY user_id, movie_id
        HAVING count(*) > 1
        ORDER BY user_id, movie_id
        """,
    ),
)


def _offline_audit() -> None:
    """Emit an SQL guard so a generated ``--sql`` script also refuses to run on unsafe data."""

    checks = "\n".join(
        f"""
    IF EXISTS ({query.strip()}) THEN
        failures := failures || E'\\n- {description}';
    END IF;"""
        for description, query in AUDIT_CHECKS
    )
    op.execute(
        f"""
DO $$
DECLARE
    failures text := '';
BEGIN{checks}
    IF failures <> '' THEN
        RAISE EXCEPTION 'Pre-flight audit failed; no columns were dropped.%', failures;
    END IF;
END $$"""
    )


def _audit() -> None:
    """Fail before any destructive change when the copies cannot be dropped safely."""

    if context.is_offline_mode():
        _offline_audit()
        return

    connection = op.get_bind()
    failures: list[str] = []
    for description, query in AUDIT_CHECKS:
        offending = connection.execute(sa.text(query)).scalars().all()
        if offending:
            sample = ", ".join(offending[:AUDIT_SAMPLE_SIZE])
            failures.append(f"- {description}: {len(offending)} row(s), e.g. {sample}")

    if failures:
        report = "\n".join(failures)
        raise RuntimeError(
            f"Pre-flight audit failed; no columns were dropped. Fix the data below and re-run the migration:\n{report}"
        )

    diverging_posters = connection.execute(
        sa.text(
            """
            SELECT count(*)
            FROM logs l
            JOIN movies m ON m.id = l.movie_id
            WHERE l.poster_path IS DISTINCT FROM m.poster_path
            """
        )
    ).scalar_one()
    if diverging_posters:
        logger.warning(
            "Dropping logs.poster_path discards %s log poster(s) that differ from their movie poster.",
            diverging_posters,
        )


def upgrade() -> None:
    """Drop the denormalized columns and key ratings on (user_id, movie_id)."""

    _audit()

    op.drop_index("ix_logs_tmdb_date_watched", table_name="logs")
    op.drop_column("logs", "tmdb_id")
    op.drop_column("logs", "poster_path")

    op.drop_constraint("uq_movie_ratings_user_tmdb", "movie_ratings", type_="unique")
    op.create_unique_constraint("uq_movie_ratings_user_movie", "movie_ratings", ["user_id", "movie_id"])
    op.drop_index("ix_movie_ratings_user_movie", table_name="movie_ratings")
    op.drop_column("movie_ratings", "tmdb_id")


def downgrade() -> None:
    """Restore the denormalized columns from movies; client-supplied posters are lost."""

    op.add_column("movie_ratings", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.execute("UPDATE movie_ratings r SET tmdb_id = m.tmdb_id FROM movies m WHERE m.id = r.movie_id")
    op.alter_column("movie_ratings", "tmdb_id", nullable=False)
    op.create_index("ix_movie_ratings_user_movie", "movie_ratings", ["user_id", "movie_id"], unique=False)
    op.drop_constraint("uq_movie_ratings_user_movie", "movie_ratings", type_="unique")
    op.create_unique_constraint("uq_movie_ratings_user_tmdb", "movie_ratings", ["user_id", "tmdb_id"])

    op.add_column("logs", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.add_column("logs", sa.Column("poster_path", sa.Text(), nullable=True))
    op.execute(
        "UPDATE logs l SET tmdb_id = m.tmdb_id, poster_path = m.poster_path FROM movies m WHERE m.id = l.movie_id"
    )
    op.alter_column("logs", "tmdb_id", nullable=False)
    op.execute("CREATE INDEX ix_logs_tmdb_date_watched ON logs (tmdb_id, date_watched DESC)")
