from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

MIGRATION_FILE = Path(__file__).resolve().parents[3] / "db_migrations" / "m001_migrate_movies.py"
spec = importlib.util.spec_from_file_location("migrate_movies_module", MIGRATION_FILE)
assert spec is not None
assert spec.loader is not None
migrate_movies = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate_movies)


class _FakeMongoCollection:
    def __init__(self, docs: list[dict]):
        self._docs = docs
        self.last_query: dict | None = None
        self.last_batch_size: int | None = None

    def find(self, query: dict, batch_size: int | None = None):
        self.last_query = query
        self.last_batch_size = batch_size
        if query == {"deleted": {"$ne": True}}:
            return iter(doc for doc in self._docs if doc.get("deleted") is not True)

        return iter(self._docs)


class _FakeMongoDB:
    def __init__(self, docs: list[dict]):
        self.movies = _FakeMongoCollection(docs)


def _mock_scalar_result(values: list[int]) -> MagicMock:
    """Build a SQLAlchemy-result-like mock whose ``.scalars().all()`` returns ``values``."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_migrate_movies_up_skips_deleted_and_missing_tmdb_id(capsys):
    mongo_db = _FakeMongoDB(
        [
            {"_id": "507f1f77bcf86cd799439011", "tmdbId": 10, "title": "A", "deleted": False},
            {"_id": "507f1f77bcf86cd799439012", "tmdbId": 11, "title": "B", "deleted": True},
            {"_id": "507f1f77bcf86cd799439013", "title": "C", "deleted": False},
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.return_value = _mock_scalar_result([10])

    await migrate_movies.up(mongo_db, pg_session, dry_run=False)

    assert mongo_db.movies.last_query == {"deleted": {"$ne": True}}
    assert mongo_db.movies.last_batch_size == migrate_movies.BATCH_SIZE
    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=2" in captured
    assert "inserted=1" in captured
    assert "skipped=1" in captured


@pytest.mark.asyncio
async def test_migrate_movies_up_dry_run_reports_progress(capsys):
    mongo_db = _FakeMongoDB([{"_id": "507f1f77bcf86cd799439011", "tmdbId": 10, "title": "A", "deleted": False}])
    pg_session = AsyncMock()
    pg_session.execute.return_value = _mock_scalar_result([])

    await migrate_movies.up(mongo_db, pg_session, dry_run=True)

    assert mongo_db.movies.last_query == {"deleted": {"$ne": True}}
    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "dry_run=True" in captured
    assert "inserted=1" in captured
    assert "skipped=0" in captured


@pytest.mark.asyncio
async def test_migrate_movies_up_dry_run_accounts_for_existing_and_prior_batch_conflicts(capsys, monkeypatch):
    monkeypatch.setattr(migrate_movies, "BATCH_SIZE", 2)

    mongo_db = _FakeMongoDB(
        [
            {"_id": "507f1f77bcf86cd799439011", "tmdbId": 10, "title": "A", "deleted": False},
            {"_id": "507f1f77bcf86cd799439012", "tmdbId": 11, "title": "B", "deleted": False},
            {"_id": "507f1f77bcf86cd799439013", "tmdbId": 10, "title": "A again", "deleted": False},
            {"_id": "507f1f77bcf86cd799439014", "tmdbId": 12, "title": "C", "deleted": False},
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([11]),
        _mock_scalar_result([]),
    ]

    await migrate_movies.up(mongo_db, pg_session, dry_run=True)

    assert pg_session.execute.await_count == 2
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "total=4" in captured
    assert "inserted=2" in captured
    assert "skipped=2" in captured
    assert "dry_run=True" in captured


@pytest.mark.asyncio
async def test_migrate_movies_up_handles_datetime_release_date():
    release_date = datetime(2024, 1, 2, 12, 30, tzinfo=UTC)
    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "tmdbId": 10,
                "title": "A",
                "releaseDate": release_date,
                "deleted": False,
            }
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.return_value = _mock_scalar_result([10])

    await migrate_movies.up(mongo_db, pg_session, dry_run=False)

    statement = pg_session.execute.await_args.args[0]
    compiled_params = statement.compile().params
    release_date_values = [v for k, v in compiled_params.items() if k.startswith("release_date")]
    assert release_date_values == [datetime(2024, 1, 2, 12, 30)]


@pytest.mark.asyncio
async def test_migrate_movies_up_flushes_in_batches(capsys, monkeypatch):
    monkeypatch.setattr(migrate_movies, "BATCH_SIZE", 2)

    mongo_db = _FakeMongoDB(
        [
            {"_id": f"507f1f77bcf86cd79943901{i}", "tmdbId": 100 + i, "title": f"M{i}", "deleted": False}
            for i in range(5)
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([100, 101]),
        _mock_scalar_result([102, 103]),
        _mock_scalar_result([104]),
    ]

    await migrate_movies.up(mongo_db, pg_session, dry_run=False)

    assert pg_session.execute.await_count == 3
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=5" in captured
    assert "inserted=5" in captured
    assert "skipped=0" in captured


@pytest.mark.asyncio
async def test_migrate_movies_down_is_noop_when_mongo_empty(capsys):
    mongo_db = _FakeMongoDB([])
    pg_session = AsyncMock()

    await migrate_movies.down(mongo_db, pg_session)

    pg_session.execute.assert_not_awaited()
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "derived_ids=0" in captured
    assert "deleted=0" in captured


@pytest.mark.asyncio
async def test_migrate_movies_down_deletes_only_derived_ids(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {"_id": "507f1f77bcf86cd799439011", "tmdbId": 10, "title": "A"},
            {"_id": "507f1f77bcf86cd799439012", "tmdbId": 11, "title": "B"},
        ]
    )

    pg_session = AsyncMock()
    delete_result = MagicMock()
    delete_result.scalars.return_value.all.return_value = [
        mongo_id_to_uuid("507f1f77bcf86cd799439011"),
        mongo_id_to_uuid("507f1f77bcf86cd799439012"),
    ]
    pg_session.execute.return_value = delete_result

    await migrate_movies.down(mongo_db, pg_session)

    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_awaited_once()

    statement = pg_session.execute.await_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert mongo_id_to_uuid("507f1f77bcf86cd799439011").hex in sql
    assert mongo_id_to_uuid("507f1f77bcf86cd799439012").hex in sql

    captured = capsys.readouterr().out
    assert "derived_ids=2" in captured
    assert "deleted=2" in captured
