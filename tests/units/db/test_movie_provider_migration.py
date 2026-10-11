"""Exercise provider separation and lossless rollback on real PostgreSQL."""

from io import StringIO

import pytest
from alembic.config import Config
from psycopg import sql
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from alembic import command
from app.types import MovieProviderName
from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "009_drop_denormalized_columns"
REVISION = "010_create_movie_providers_table"


def _seed(harness: AlembicTestHarness):
    harness.upgrade(PREVIOUS_REVISION)
    with harness.connect() as conn:
        user_id = conn.execute(
            """INSERT INTO users (email, handle, first_name, last_name, profile_visibility)
            VALUES ('mapping@example.com', 'mapping', 'Movie', 'User', 'private') RETURNING id"""
        ).fetchone()[0]
        ids = []
        for source_id, deleted, payload, synced in [
            (550, False, '{"title":"Original", "nested": {"score": 8}}', "2024-01-01T12:00:00+02:00"),
            (551, True, '{"deleted": true}', None),
            (552, False, None, None),
        ]:
            movie_id = conn.execute(
                """INSERT INTO movies (tmdb_id, title, deleted, deleted_at, tmdb_payload, tmdb_last_synced_at)
                VALUES (%s, 'Saved title', %s, CASE WHEN %s THEN now() ELSE NULL END, %s::jsonb, %s)
                RETURNING id""",
                (source_id, deleted, deleted, payload, synced),
            ).fetchone()[0]
            ids.append(movie_id)
            conn.execute(
                """INSERT INTO logs (user_id, movie_id, date_watched, viewing_notes, deleted)
                VALUES (%s, %s, now(), 'User-authored note', %s)""",
                (user_id, movie_id, deleted),
            )
            conn.execute(
                """INSERT INTO movie_ratings (user_id, movie_id, rating, review, deleted)
                VALUES (%s, %s, 9, 'User-authored review', %s)""",
                (user_id, movie_id, deleted),
            )
    return ids


def _rows(harness, table):
    # The table is selected only by test code, never by application input.
    with harness.connect() as conn:
        query = sql.SQL("SELECT row_to_json(t) FROM {} t ORDER BY id").format(sql.Identifier(table))
        return [row[0] for row in conn.execute(query).fetchall()]


def _offline(harness, *, downgrade=False):
    output = StringIO()
    config = Config(harness.config.config_file_name, output_buffer=output)
    config.set_main_option("script_location", harness.config.get_main_option("script_location"))
    if downgrade:
        command.downgrade(config, f"{REVISION}:{PREVIOUS_REVISION}", sql=True)
    else:
        command.upgrade(config, f"{PREVIOUS_REVISION}:{REVISION}", sql=True)
    return output.getvalue()


@pytest.mark.parametrize("offline", [False, True])
def test_backfill_and_rollback_preserve_every_movie_and_user_row(alembic_test_harness, offline):
    harness = alembic_test_harness
    _seed(harness)
    before = {table: _rows(harness, table) for table in ("movies", "users", "logs", "movie_ratings")}
    if offline:
        with harness.connect() as conn:
            conn.execute(_offline(harness))
    else:
        harness.upgrade(REVISION)

    source_columns = {"tmdb_id", "tmdb_payload", "tmdb_last_synced_at"}
    assert _rows(harness, "movies") == [
        {key: value for key, value in movie.items() if key not in source_columns} for movie in before["movies"]
    ]
    for table in ("users", "logs", "movie_ratings"):
        assert _rows(harness, table) == before[table]
    with harness.connect() as conn:
        mappings = conn.execute(
            "SELECT movie_id::text, provider, external_id, payload, last_synced_at FROM movie_providers"
        ).fetchall()
        assert len(mappings) == len(before["movies"])
        for movie_id, provider, external_id, payload, observed in mappings:
            original = next(movie for movie in before["movies"] if movie["id"] == movie_id)
            assert provider == "tmdb"
            assert external_id == str(original["tmdb_id"])
            assert payload == original["tmdb_payload"]
            if observed is None:
                assert original["tmdb_last_synced_at"] is None
            else:
                assert observed.isoformat() == original["tmdb_last_synced_at"]

    if offline:
        with harness.connect() as conn:
            conn.execute(_offline(harness, downgrade=True))
    else:
        harness.downgrade(PREVIOUS_REVISION)
    for table, rows in before.items():
        assert _rows(harness, table) == rows


@pytest.mark.parametrize(
    ("provider", "external_id", "movie_index", "error"),
    [
        ("tmdb", "550", 1, UniqueViolation),
        ("tmdb", "999", 0, UniqueViolation),
        ("tmdb", "", 0, CheckViolation),
        ("tmdb", "   ", 0, CheckViolation),
        ("unknown", "550", 0, CheckViolation),
        ("tmdb", "999", None, ForeignKeyViolation),
    ],
)
def test_mapping_constraints(alembic_test_harness, provider, external_id, movie_index, error):
    from uuid import uuid4

    ids = _seed(alembic_test_harness)
    alembic_test_harness.upgrade(REVISION)
    movie_id = ids[movie_index] if movie_index is not None else uuid4()
    with alembic_test_harness.connect() as conn, pytest.raises(error):
        conn.execute(
            "INSERT INTO movie_providers (provider, external_id, movie_id) VALUES (%s, %s, %s)",
            (provider, external_id, movie_id),
        )


@pytest.mark.parametrize("provider", list(MovieProviderName))
def test_latest_schema_accepts_every_registered_provider(alembic_test_harness, provider):
    alembic_test_harness.upgrade()
    with alembic_test_harness.connect() as conn:
        movie_id = conn.execute("INSERT INTO movies (title) VALUES ('New film') RETURNING id").fetchone()[0]
        conn.execute(
            "INSERT INTO movie_providers (provider, external_id, movie_id) VALUES (%s, '550', %s)",
            (provider.value, movie_id),
        )
        assert conn.execute("SELECT provider FROM movie_providers WHERE movie_id = %s", (movie_id,)).fetchone() == (
            provider.value,
        )


def test_distinct_providers_can_share_a_movie_and_use_uuid_ids(alembic_test_harness):
    from uuid import uuid4

    ids = _seed(alembic_test_harness)
    alembic_test_harness.upgrade(REVISION)
    external_id = str(uuid4())
    with alembic_test_harness.connect() as conn:
        # Simulate a future allowlist extension without adding a provider to production.
        conn.execute("ALTER TABLE movie_providers DROP CONSTRAINT ck_movie_providers_provider")
        conn.execute(
            "INSERT INTO movie_providers (provider, external_id, movie_id) VALUES ('future', %s, %s)",
            (external_id, ids[0]),
        )
        assert conn.execute(
            "SELECT provider, external_id FROM movie_providers WHERE movie_id = %s ORDER BY provider", (ids[0],)
        ).fetchall() == [("future", external_id), ("tmdb", "550")]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("missing", "no TMDB mapping"),
        ("provider", "additional providers"),
        ("uuid", "not a legacy integer"),
        ("2147483648", "not a legacy integer"),
        ("-2147483649", "not a legacy integer"),
        ("999999999999999999999999999999", "not a legacy integer"),
        ("0550", "integer conversion would change"),
        ("0551", "collide after integer conversion"),
    ],
)
@pytest.mark.parametrize("offline", [False, True])
def test_unsafe_rollback_keeps_the_new_schema_and_data(alembic_test_harness, change, message, offline):
    harness = alembic_test_harness
    ids = _seed(harness)
    harness.upgrade(REVISION)
    with harness.connect() as conn:
        if change == "missing":
            conn.execute("DELETE FROM movie_providers WHERE movie_id = %s", (ids[0],))
        elif change == "provider":
            conn.execute("ALTER TABLE movie_providers DROP CONSTRAINT ck_movie_providers_provider")
            conn.execute("UPDATE movie_providers SET provider = 'future' WHERE movie_id = %s", (ids[0],))
        else:
            conn.execute("UPDATE movie_providers SET external_id = %s WHERE movie_id = %s", (change, ids[0]))
        before = conn.execute("SELECT * FROM movie_providers ORDER BY movie_id").fetchall()
    if offline:
        script = _offline(harness, downgrade=True)
        with harness.connect() as conn, pytest.raises(Exception, match=message):
            conn.execute(script)
    else:
        with pytest.raises(Exception, match=message):
            harness.downgrade(PREVIOUS_REVISION)
    with harness.connect() as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == REVISION
        assert conn.execute("SELECT * FROM movie_providers ORDER BY movie_id").fetchall() == before
        assert (
            conn.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'movies' AND column_name = 'tmdb_id'"
            ).fetchone()[0]
            == 0
        )
