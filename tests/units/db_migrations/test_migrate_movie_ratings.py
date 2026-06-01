from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

MIGRATION_FILE = Path(__file__).resolve().parents[3] / "db_migrations" / "m003_migrate_movie_ratings.py"
spec = importlib.util.spec_from_file_location("migrate_movie_ratings_module", MIGRATION_FILE)
assert spec is not None
assert spec.loader is not None
migrate_movie_ratings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate_movie_ratings)


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
        self.movie_ratings = _FakeMongoCollection(docs)


def _mock_scalar_result(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _mock_query_result(rows: list[tuple[object, object]]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_migrate_movie_ratings_up_skips_deleted_and_missing_foreign_keys(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    valid_user_id = mongo_id_to_uuid("507f1f77bcf86cd799439021")
    valid_movie_id = mongo_id_to_uuid("507f1f77bcf86cd799439031")
    missing_user_id = mongo_id_to_uuid("507f1f77bcf86cd799439022")

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "rating": 8,
                "review": "Valid",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "userId": "507f1f77bcf86cd799439022",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 551,
                "rating": 6,
                "review": "Missing user",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439013",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 552,
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

    await migrate_movie_ratings.up(mongo_db, pg_session, dry_run=False)

    assert mongo_db.movie_ratings.last_query == {"deleted": {"$ne": True}}
    assert mongo_db.movie_ratings.last_batch_size == migrate_movie_ratings.BATCH_SIZE
    assert pg_session.execute.await_count == 3
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert str(missing_user_id) not in captured
    assert "warnings=1" in captured
    assert "inserted=1" in captured
    assert "skipped=1" in captured


@pytest.mark.asyncio
async def test_migrate_movie_ratings_up_dry_run_reports_progress(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "rating": 8,
                "review": "Valid",
                "deleted": False,
            }
        ]
    )
    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439021")]),
        _mock_scalar_result([mongo_id_to_uuid("507f1f77bcf86cd799439031")]),
        _mock_query_result([]),
    ]

    await migrate_movie_ratings.up(mongo_db, pg_session, dry_run=True)

    assert pg_session.execute.await_count == 3
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "dry_run=True" in captured
    assert "inserted=1" in captured
    assert "skipped=0" in captured
    assert "warnings=0" in captured


@pytest.mark.asyncio
async def test_migrate_movie_ratings_up_dry_run_accounts_for_existing_and_prior_batch_conflicts(
    capsys, monkeypatch
):
    from app.utils.id_utils import mongo_id_to_uuid

    monkeypatch.setattr(migrate_movie_ratings, "BATCH_SIZE", 2)

    user_a = "507f1f77bcf86cd799439021"
    user_b = "507f1f77bcf86cd799439022"
    movie_a = "507f1f77bcf86cd799439031"
    movie_b = "507f1f77bcf86cd799439032"
    user_a_uuid = mongo_id_to_uuid(user_a)
    user_b_uuid = mongo_id_to_uuid(user_b)
    movie_a_uuid = mongo_id_to_uuid(movie_a)
    movie_b_uuid = mongo_id_to_uuid(movie_b)

    mongo_db = _FakeMongoDB(
        [
            {"_id": "507f1f77bcf86cd799439011", "userId": user_a, "movieId": movie_a, "tmdbId": 550, "deleted": False},
            {"_id": "507f1f77bcf86cd799439012", "userId": user_a, "movieId": movie_b, "tmdbId": 551, "deleted": False},
            {"_id": "507f1f77bcf86cd799439013", "userId": user_a, "movieId": movie_a, "tmdbId": 550, "deleted": False},
            {"_id": "507f1f77bcf86cd799439014", "userId": user_b, "movieId": movie_b, "tmdbId": 552, "deleted": False},
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result([user_a_uuid]),
        _mock_scalar_result([movie_a_uuid, movie_b_uuid]),
        _mock_query_result([(user_a_uuid, 551)]),
        _mock_scalar_result([user_a_uuid, user_b_uuid]),
        _mock_scalar_result([movie_a_uuid, movie_b_uuid]),
        _mock_query_result([]),
    ]

    await migrate_movie_ratings.up(mongo_db, pg_session, dry_run=True)

    assert pg_session.execute.await_count == 6
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "total=4" in captured
    assert "inserted=2" in captured
    assert "skipped=2" in captured
    assert "warnings=0" in captured


@pytest.mark.asyncio
async def test_migrate_movie_ratings_up_preserves_rating_review_and_timestamps():
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 550,
                "rating": 9,
                "review": "Excellent",
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

    await migrate_movie_ratings.up(mongo_db, pg_session, dry_run=False)

    statement = pg_session.execute.await_args_list[2].args[0]
    compiled_params = statement.compile().params
    assert [value for key, value in compiled_params.items() if key.startswith("rating")] == [9]
    assert [value for key, value in compiled_params.items() if key.startswith("review")] == ["Excellent"]
    assert [value for key, value in compiled_params.items() if key.startswith("created_at")] == [
        datetime(2024, 1, 3, 9, 0, tzinfo=UTC)
    ]
    assert [value for key, value in compiled_params.items() if key.startswith("updated_at")] == [
        datetime(2024, 1, 4, 9, 0, tzinfo=UTC)
    ]


@pytest.mark.asyncio
async def test_migrate_movie_ratings_up_flushes_in_batches(capsys, monkeypatch):
    from app.utils.id_utils import mongo_id_to_uuid

    monkeypatch.setattr(migrate_movie_ratings, "BATCH_SIZE", 2)
    mongo_db = _FakeMongoDB(
        [
            {
                "_id": f"507f1f77bcf86cd79943901{i}",
                "userId": "507f1f77bcf86cd799439021",
                "movieId": "507f1f77bcf86cd799439031",
                "tmdbId": 600 + i,
                "rating": 7,
                "deleted": False,
            }
            for i in range(5)
        ]
    )

    user_uuid = mongo_id_to_uuid("507f1f77bcf86cd799439021")
    movie_uuid = mongo_id_to_uuid("507f1f77bcf86cd799439031")

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

    await migrate_movie_ratings.up(mongo_db, pg_session, dry_run=False)

    assert pg_session.execute.await_count == 9
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=5" in captured
    assert "inserted=5" in captured
    assert "skipped=0" in captured
    assert "warnings=0" in captured


@pytest.mark.asyncio
async def test_migrate_movie_ratings_down_is_noop_when_mongo_empty(capsys):
    mongo_db = _FakeMongoDB([])
    pg_session = AsyncMock()

    await migrate_movie_ratings.down(mongo_db, pg_session)

    pg_session.execute.assert_not_awaited()
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "derived_ids=0" in captured
    assert "deleted=0" in captured


@pytest.mark.asyncio
async def test_migrate_movie_ratings_down_deletes_only_derived_ids(capsys):
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

    await migrate_movie_ratings.down(mongo_db, pg_session)

    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_awaited_once()

    statement = pg_session.execute.await_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert mongo_id_to_uuid("507f1f77bcf86cd799439011").hex in sql
    assert mongo_id_to_uuid("507f1f77bcf86cd799439012").hex in sql

    captured = capsys.readouterr().out
    assert "derived_ids=2" in captured
    assert "deleted=2" in captured
