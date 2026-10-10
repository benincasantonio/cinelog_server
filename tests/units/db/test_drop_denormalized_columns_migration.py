"""PostgreSQL integration tests for dropping the denormalized movie columns."""

from io import StringIO
from uuid import UUID

import pytest
from alembic.config import Config
from psycopg.errors import RaiseException, UniqueViolation

from alembic import command
from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "008_add_locale_to_users"


def _insert_user(harness: AlembicTestHarness, *, suffix: str) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name)
            VALUES (%s, %s, 'Denorm', 'User')
            RETURNING id
            """,
            (f"denorm-{suffix}@example.com", f"denorm-{suffix}"),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_movie(harness: AlembicTestHarness, *, tmdb_id: int, poster_path: str | None = "/movie.jpg") -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            "INSERT INTO movies (tmdb_id, title, poster_path) VALUES (%s, %s, %s) RETURNING id",
            (tmdb_id, f"Movie {tmdb_id}", poster_path),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_legacy_log(
    harness: AlembicTestHarness,
    *,
    user_id: UUID,
    movie_id: UUID,
    tmdb_id: int,
    poster_path: str | None = "/movie.jpg",
) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO logs (user_id, movie_id, tmdb_id, date_watched, poster_path)
            VALUES (%s, %s, %s, now(), %s)
            RETURNING id
            """,
            (user_id, movie_id, tmdb_id, poster_path),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_legacy_rating(harness: AlembicTestHarness, *, user_id: UUID, movie_id: UUID, tmdb_id: int) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO movie_ratings (user_id, movie_id, tmdb_id, rating)
            VALUES (%s, %s, %s, 8)
            RETURNING id
            """,
            (user_id, movie_id, tmdb_id),
        ).fetchone()
    assert row is not None
    return row[0]


def _columns(harness: AlembicTestHarness, table: str) -> set[str]:
    with harness.connect() as connection:
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        ).fetchall()
    return {row[0] for row in rows}


def _indexes(harness: AlembicTestHarness, table: str) -> set[str]:
    with harness.connect() as connection:
        rows = connection.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s", (table,)).fetchall()
    return {row[0] for row in rows}


def _current_revision(harness: AlembicTestHarness) -> str:
    with harness.connect() as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row is not None
    return row[0]


def test_migration_drops_copies_and_keys_ratings_on_movie(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    user_id = _insert_user(alembic_test_harness, suffix="consistent")
    movie_id = _insert_movie(alembic_test_harness, tmdb_id=550)
    log_id = _insert_legacy_log(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=550)
    rating_id = _insert_legacy_rating(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=550)

    alembic_test_harness.upgrade()

    assert {"tmdb_id", "poster_path"}.isdisjoint(_columns(alembic_test_harness, "logs"))
    assert "tmdb_id" not in _columns(alembic_test_harness, "movie_ratings")
    assert "ix_logs_tmdb_date_watched" not in _indexes(alembic_test_harness, "logs")
    rating_indexes = _indexes(alembic_test_harness, "movie_ratings")
    assert "uq_movie_ratings_user_movie" in rating_indexes
    assert {"uq_movie_ratings_user_tmdb", "ix_movie_ratings_user_movie"}.isdisjoint(rating_indexes)

    with alembic_test_harness.connect() as connection:
        assert connection.execute("SELECT id FROM logs").fetchall() == [(log_id,)]
        assert connection.execute("SELECT id FROM movie_ratings").fetchall() == [(rating_id,)]
        with pytest.raises(UniqueViolation):
            connection.execute(
                "INSERT INTO movie_ratings (user_id, movie_id, rating) VALUES (%s, %s, 5)",
                (user_id, movie_id),
            )


@pytest.mark.parametrize(
    ("seed", "expected_check"),
    [
        ("log", "logs.tmdb_id disagrees with movies.tmdb_id"),
        ("rating", "movie_ratings.tmdb_id disagrees with movies.tmdb_id"),
    ],
)
def test_migration_audit_rejects_copies_that_disagree_with_their_movie(
    alembic_test_harness: AlembicTestHarness,
    seed: str,
    expected_check: str,
):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    user_id = _insert_user(alembic_test_harness, suffix=seed)
    movie_id = _insert_movie(alembic_test_harness, tmdb_id=550)
    if seed == "log":
        offending_id = _insert_legacy_log(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=999)
    else:
        offending_id = _insert_legacy_rating(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=999)

    with pytest.raises(RuntimeError) as error:
        alembic_test_harness.upgrade()

    message = str(error.value)
    assert "Pre-flight audit failed" in message
    assert expected_check in message
    assert str(offending_id) in message
    assert _current_revision(alembic_test_harness) == PREVIOUS_REVISION
    assert "tmdb_id" in _columns(alembic_test_harness, "logs")


def test_migration_audit_rejects_duplicate_ratings_for_one_movie(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    user_id = _insert_user(alembic_test_harness, suffix="duplicate")
    movie_id = _insert_movie(alembic_test_harness, tmdb_id=550)
    _insert_legacy_rating(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=550)
    _insert_legacy_rating(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=551)

    with pytest.raises(RuntimeError) as error:
        alembic_test_harness.upgrade()

    message = str(error.value)
    assert "more than one movie_ratings row per (user_id, movie_id)" in message
    assert f"{user_id}/{movie_id}" in message
    assert _current_revision(alembic_test_harness) == PREVIOUS_REVISION


def test_migration_downgrade_backfills_copies_from_movies(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    user_id = _insert_user(alembic_test_harness, suffix="rollback")
    movie_id = _insert_movie(alembic_test_harness, tmdb_id=550, poster_path="/movie.jpg")
    _insert_legacy_log(
        alembic_test_harness,
        user_id=user_id,
        movie_id=movie_id,
        tmdb_id=550,
        poster_path="/client-supplied.jpg",
    )
    _insert_legacy_rating(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=550)
    alembic_test_harness.upgrade()

    alembic_test_harness.downgrade(PREVIOUS_REVISION)

    with alembic_test_harness.connect() as connection:
        assert connection.execute("SELECT tmdb_id, poster_path FROM logs").fetchall() == [(550, "/movie.jpg")]
        assert connection.execute("SELECT tmdb_id FROM movie_ratings").fetchall() == [(550,)]
        nullable = connection.execute(
            """
            SELECT table_name, is_nullable
            FROM information_schema.columns
            WHERE column_name = 'tmdb_id' AND table_name IN ('logs', 'movie_ratings')
            ORDER BY table_name
            """
        ).fetchall()
        assert nullable == [("logs", "NO"), ("movie_ratings", "NO")]
        with pytest.raises(UniqueViolation):
            connection.execute(
                "INSERT INTO movie_ratings (user_id, movie_id, tmdb_id, rating) VALUES (%s, %s, 550, 5)",
                (user_id, movie_id),
            )

    assert "ix_logs_tmdb_date_watched" in _indexes(alembic_test_harness, "logs")
    rating_indexes = _indexes(alembic_test_harness, "movie_ratings")
    assert {"uq_movie_ratings_user_tmdb", "ix_movie_ratings_user_movie"} <= rating_indexes
    assert "uq_movie_ratings_user_movie" not in rating_indexes


def _offline_audit_sql(harness: AlembicTestHarness) -> str:
    buffer = StringIO()
    offline_config = Config(harness.config.config_file_name, output_buffer=buffer)
    offline_config.set_main_option("script_location", harness.config.get_main_option("script_location"))
    command.upgrade(offline_config, f"{PREVIOUS_REVISION}:head", sql=True)
    script = buffer.getvalue()
    start = script.index("DO $$")
    end = script.index("END $$", start) + len("END $$")
    return script[start:end]


def test_offline_migration_script_guards_against_unsafe_data(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    guard = _offline_audit_sql(alembic_test_harness)
    user_id = _insert_user(alembic_test_harness, suffix="offline")
    movie_id = _insert_movie(alembic_test_harness, tmdb_id=550)

    with alembic_test_harness.connect() as connection:
        connection.execute(guard)

    _insert_legacy_rating(alembic_test_harness, user_id=user_id, movie_id=movie_id, tmdb_id=999)

    with alembic_test_harness.connect() as connection, pytest.raises(RaiseException) as error:
        connection.execute(guard)

    assert "movie_ratings.tmdb_id disagrees with movies.tmdb_id" in str(error.value)
