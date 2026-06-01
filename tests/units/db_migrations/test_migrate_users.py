from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

MIGRATION_FILE = Path(__file__).resolve().parents[3] / "db_migrations" / "m002_migrate_users.py"
spec = importlib.util.spec_from_file_location("migrate_users_module", MIGRATION_FILE)
assert spec is not None
assert spec.loader is not None
migrate_users = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate_users)


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
        self.users = _FakeMongoCollection(docs)


def _mock_scalar_result(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _mock_query_result(rows: list[tuple[str, str]]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_migrate_users_up_skips_deleted_and_duplicate_rows(capsys):
    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "handle": "first",
                "firstName": "First",
                "lastName": "User",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "email": "deleted@example.com",
                "handle": "deleted",
                "firstName": "Deleted",
                "lastName": "User",
                "deleted": True,
            },
            {
                "_id": "507f1f77bcf86cd799439013",
                "email": "USER@example.com",
                "handle": "second",
                "firstName": "Second",
                "lastName": "User",
                "deleted": False,
            },
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.return_value = _mock_scalar_result(["inserted-user-id"])

    await migrate_users.up(mongo_db, pg_session, dry_run=False)

    assert mongo_db.users.last_query == {"deleted": {"$ne": True}}
    assert mongo_db.users.last_batch_size == migrate_users.BATCH_SIZE
    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=2" in captured
    assert "inserted=1" in captured
    assert "skipped=1" in captured


@pytest.mark.asyncio
async def test_migrate_users_up_dry_run_reports_progress(capsys):
    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "handle": "userhandle",
                "firstName": "Test",
                "lastName": "User",
                "deleted": False,
            }
        ]
    )
    pg_session = AsyncMock()
    pg_session.execute.return_value = _mock_query_result([])

    await migrate_users.up(mongo_db, pg_session, dry_run=True)

    assert mongo_db.users.last_query == {"deleted": {"$ne": True}}
    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "dry_run=True" in captured
    assert "inserted=1" in captured
    assert "skipped=0" in captured


@pytest.mark.asyncio
async def test_migrate_users_up_dry_run_accounts_for_existing_and_prior_batch_conflicts(capsys, monkeypatch):
    monkeypatch.setattr(migrate_users, "BATCH_SIZE", 2)

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "handle": "available",
                "firstName": "A",
                "lastName": "User",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "email": "other@example.com",
                "handle": "taken",
                "firstName": "B",
                "lastName": "User",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439013",
                "email": "USER@example.com",
                "handle": "new-handle",
                "firstName": "C",
                "lastName": "User",
                "deleted": False,
            },
            {
                "_id": "507f1f77bcf86cd799439014",
                "email": "third@example.com",
                "handle": "third-handle",
                "firstName": "D",
                "lastName": "User",
                "deleted": False,
            },
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_query_result([("someone@example.com", "taken")]),
        _mock_query_result([]),
    ]

    await migrate_users.up(mongo_db, pg_session, dry_run=True)

    assert pg_session.execute.await_count == 2
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "total=4" in captured
    assert "inserted=2" in captured
    assert "skipped=2" in captured
    assert "dry_run=True" in captured


@pytest.mark.asyncio
async def test_migrate_users_up_normalizes_datetime_date_of_birth():
    mongo_db = _FakeMongoDB(
        [
            {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "handle": "userhandle",
                "firstName": "Test",
                "lastName": "User",
                "dateOfBirth": datetime(1990, 1, 2, 12, 30, tzinfo=UTC),
                "createdAt": datetime(2024, 1, 3, 9, 0, tzinfo=UTC),
                "updatedAt": datetime(2024, 1, 4, 9, 0, tzinfo=UTC),
                "deleted": False,
            }
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.return_value = _mock_scalar_result(["inserted-user-id"])

    await migrate_users.up(mongo_db, pg_session, dry_run=False)

    statement = pg_session.execute.await_args.args[0]
    compiled_params = statement.compile().params
    date_of_birth_values = [value for key, value in compiled_params.items() if key.startswith("date_of_birth")]
    assert date_of_birth_values == [date(1990, 1, 2)]


@pytest.mark.asyncio
async def test_migrate_users_up_flushes_in_batches(capsys, monkeypatch):
    monkeypatch.setattr(migrate_users, "BATCH_SIZE", 2)

    mongo_db = _FakeMongoDB(
        [
            {
                "_id": f"507f1f77bcf86cd79943901{i}",
                "email": f"user{i}@example.com",
                "handle": f"user{i}",
                "firstName": "Batch",
                "lastName": "User",
                "deleted": False,
            }
            for i in range(5)
        ]
    )

    pg_session = AsyncMock()
    pg_session.execute.side_effect = [
        _mock_scalar_result(["a", "b"]),
        _mock_scalar_result(["c", "d"]),
        _mock_scalar_result(["e"]),
    ]

    await migrate_users.up(mongo_db, pg_session, dry_run=False)

    assert pg_session.execute.await_count == 3
    pg_session.commit.assert_awaited_once()

    captured = capsys.readouterr().out
    assert "total=5" in captured
    assert "inserted=5" in captured
    assert "skipped=0" in captured


@pytest.mark.asyncio
async def test_migrate_users_down_is_noop_when_mongo_empty(capsys):
    mongo_db = _FakeMongoDB([])
    pg_session = AsyncMock()

    await migrate_users.down(mongo_db, pg_session)

    pg_session.execute.assert_not_awaited()
    pg_session.commit.assert_not_awaited()

    captured = capsys.readouterr().out
    assert "derived_ids=0" in captured
    assert "deleted=0" in captured


@pytest.mark.asyncio
async def test_migrate_users_down_deletes_only_derived_ids(capsys):
    from app.utils.id_utils import mongo_id_to_uuid

    mongo_db = _FakeMongoDB(
        [
            {"_id": "507f1f77bcf86cd799439011", "email": "a@example.com"},
            {"_id": "507f1f77bcf86cd799439012", "email": "b@example.com"},
        ]
    )

    pg_session = AsyncMock()
    delete_result = MagicMock()
    delete_result.scalars.return_value.all.return_value = [
        mongo_id_to_uuid("507f1f77bcf86cd799439011"),
        mongo_id_to_uuid("507f1f77bcf86cd799439012"),
    ]
    pg_session.execute.return_value = delete_result

    await migrate_users.down(mongo_db, pg_session)

    pg_session.execute.assert_awaited_once()
    pg_session.commit.assert_awaited_once()

    statement = pg_session.execute.await_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert mongo_id_to_uuid("507f1f77bcf86cd799439011").hex in sql
    assert mongo_id_to_uuid("507f1f77bcf86cd799439012").hex in sql

    captured = capsys.readouterr().out
    assert "derived_ids=2" in captured
    assert "deleted=2" in captured
