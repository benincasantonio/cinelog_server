from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

MIGRATION_FILE = Path(__file__).resolve().parents[3] / "db_migrations" / "m004_migrate_logs.py"
spec = importlib.util.spec_from_file_location("migrate_logs_module", MIGRATION_FILE)
assert spec is not None
assert spec.loader is not None
migrate_logs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate_logs)


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
        self.logs = _FakeMongoCollection(docs)


def _mock_scalar_result(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_migrate_logs_up_skips_deleted_missing_foreign_keys_and_invalid_dates(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    valid_user_id = mongo_id_to_uuid("507f1f77bcf86cd799439021")
    valid_movie_id = mongo_id_to_uuid("507f1f77bcf86cd799439031")

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "dateWatched": "2024-01-02",
                "watchedWhere": "cinema",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "userId": "507f1f77bcf86cd799439022",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 551,
                "dateWatched": "2024-01-03",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439013",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 552,
                "dateWatched": "not-a-date",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439014",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 553,
                "dateWatched": "2024-01-04",
                "deleted": True,
            },
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([valid_user_id]),
        _mock_scalar_result([valid_movie_id]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439011")]),
    ]

    await migrate_logs.up(mongo_db, pg_session, dry_run=False)

    assert mongo_db.logs.last_query == {"deleted": {"$ne": True}}
    assert mongo_db.logs.last_batch_size == migrate_logs.BATCH_SIZE
    assert pg_session.execute.await_count == 3
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=3" in captured
    assert "inserted=1" in captured
    assert "skipped=2" in captured
    assert "warnings=2" in captured


@pytest.mark.asyncio
async def test_migrate_logs_up_dry_run_reports_progress(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "dateWatched": "2024-01-02",
                "deleted": False,
            }
        ]
    )
    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439021")]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439031")]),
        _mock_scalar_result([]),
    ]

    await migrate_logs.up(mongo_db, pg_session, dry_run=True)

    assert pg_session.execute.await_count == 3
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "dry_run=True" in captured
    assert "inserted=1" in captured
    assert "skipped=0" in captured
    assert "warnings=0" in captured


@pytest.mark.asyncio
async def test_migrate_logs_up_dry_run_accounts_for_existing_and_prior_batch_conflicts(capsys, monkeypatch):
    from app.utils.id_utils import mongo_id_to_uuid

    monkeypatch.setattr(migrate_logs, "BATCH_SIZE", 2)
    user_uuid = mongo_id_to_uuid("507f1f77bcf86cd799439021")
    movie_uuid = mongo_id_to_uuid("507f1f77bcf86cd799439031")

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "dateWatched": "2024-01-02",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 551,
                "dateWatched": "2024-01-03",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 552,
                "dateWatched": "2024-01-04",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439013",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 553,
                "dateWatched": "2024-01-05",
                "deleted": False,
            },
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([user_uuid]),
        _mock_scalar_result([movie_uuid]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439012")]),
        _mock_scalar_result([user_uuid]),
        _mock_scalar_result([movie_uuid]),
        _mock_scalar_result([]),
    ]

    await migrate_logs.up(mongo_db, pg_session, dry_run=True)

    assert pg_session.execute.await_count == 6
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "total=4" in captured
    assert "inserted=2" in captured
    assert "skipped=2" in captured
    assert "warnings=0" in captured


@pytest.mark.asyncio
async def test_migrate_logs_up_preserves_fields_and_normalizes_invalid_watched_where():
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "dateWatched": "2024-01-03",
                "viewingNotes": "Great notes",
                "posterPath": "/poster.jpg",
                "watchedWhere": "unsupported",
                "createdAt": datetime(2024, 1, 3, 9, 0, tzinfo=UTC),
                "updatedAt": datetime(2024, 1, 4, 9, 0, tzinfo=UTC),
                "deleted": False,
            }
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439021")]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439031")]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439011")]),
    ]

    await migrate_logs.up(mongo_db, pg_session, dry_run=False)

    statement = pg_session.execute.await_args_list[2].args[0]
    compiled_params = statement.compile().params
    assert [value for key, value in compiled_params.items() if key.startswith("watched_where")] == ["other"]
    assert [value for key, value in compiled_params.items() if key.startswith("viewing_notes")] == ["Great notes"]
    assert [value for key, value in compiled_params.items() if key.startswith("poster_path")] == ["/poster.jpg"]
    assert [value for key, value in compiled_params.items() if key.startswith("date_watched")] == [
        datetime(2024, 1, 3, tzinfo=UTC)
    ]


@pytest.mark.asyncio
async def test_migrate_logs_up_flushes_in_batches(capsys, monkeypatch):
    from app.utils.id_utils import mongo_id_to_uuid

    monkeypatch.setattr(migrate_logs, "BATCH_SIZE", 2)
    user_uuid = mongo_id_to_uuid("507f1f77bcf86cd799439021")
    movie_uuid = mongo_id_to_uuid("507f1f77bcf86cd799439031")

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": f"507f1f77bcf86cd79943901{i}",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 600 + i,
                "dateWatched": "2024-01-02",
                "deleted": False,
            }
            for i in range(5)
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([user_uuid]),
        _mock_scalar_result([movie_uuid]),
        _mock_scalar_result(
            [
                mongo_id_to_uuid("507f1f77bcf86cd799439010"),
                mongo_id_to_uuid("507f1f77bcf86cd799439011"),
            ]
        ),
        _mock_scalar_result([user_uuid]),
        _mock_scalar_result([movie_uuid]),
        _mock_scalar_result(
            [
                mongo_id_to_uuid("507f1f77bcf86cd799439012"),
                mongo_id_to_uuid("507f1f77bcf86cd799439013"),
            ]
        ),
        _mock_scalar_result([user_uuid]),
        _mock_scalar_result([movie_uuid]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439014")]),
    ]

    await migrate_logs.up(mongo_db, pg_session, dry_run=False)

    assert pg_session.execute.await_count == 9
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=5" in captured
    assert "inserted=5" in captured
    assert "skipped=0" in captured
    assert "warnings=0" in captured


@pytest.mark.asyncio
async def test_migrate_logs_down_is_noop_when_mongo_empty(capsys):
    mongo_db = _FakeMongoDB([])
    pg_session = AsyncMock()

    await migrate_logs.down(mongo_db, pg_session)

    pg_session.execute.assert_not_awaited()
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "derived_ids=0" in captured
    assert "deleted=0" in captured


@pytest.mark.asyncio
async def test_migrate_logs_down_deletes_only_derived_ids(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {"_id": "507f1f77bcf86cd799439011"},
            {"_id": "507f1f77bcf86cd799439012"},
        ]
    )
    pg_session = AsyncMock()
    delete_result = MagicMock()
    delete_result.scalars.return_value.all.return_value = [
        mongo_id_to_uuid("507f1f77bcf86cd799439011"),
        mongo_id_to_uuid("507f1f77bcf86cd799439012"),
    ]
    pg_session.execute.return_value = delete_result

    await migrate_logs.down(mongo_db, pg_session)

    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_awaited_once()

    statement = pg_session.execute.await_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert mongo_id_to_uuid("507f1f77bcf86cd799439011").hex in sql
    assert mongo_id_to_uuid("507f1f77bcf86cd799439012").hex in sql

    captured = capsys.readouterr().out
    assert "derived_ids=2" in captured
    assert "deleted=2" in captured
