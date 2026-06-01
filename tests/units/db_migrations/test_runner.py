from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from db_migrations import runner


def test_migration_id():
    assert runner._migration_id("001", "migrate_movies") == "001_migrate_movies"


def test_get_pending_migrations():
    applied = {"001_first"}
    discovered = [("001", "first"), ("002", "second"), ("003", "third")]

    pending = runner._get_pending_migrations(applied, discovered)

    assert pending == [("002", "second"), ("003", "third")]


def test_discover_migrations_filters_and_sorts(monkeypatch):
    monkeypatch.setattr(runner.Path, "exists", lambda _: True)
    monkeypatch.setattr(
        runner.os,
        "listdir",
        lambda _: [
            "m003_third.py",
            "notes.txt",
            "m001_first.py",
            "__init__.py",
            "runner.py",
            "m002_second.py",
        ],
    )

    discovered = runner._discover_migrations()

    assert discovered == [("001", "first"), ("002", "second"), ("003", "third")]


@pytest.mark.asyncio
async def test_run_pending_migrations_dry_run(monkeypatch):
    async def _applied_versions(_session):
        return {"001_first"}

    monkeypatch.setattr(runner, "_get_applied_versions", _applied_versions)
    monkeypatch.setattr(runner, "_discover_migrations", lambda: [("001", "first"), ("002", "second")])

    calls: list[tuple[str, str, bool]] = []

    async def _run_up(_mongo_db, _pg_session, version, module_name, dry_run=False):
        calls.append((version, module_name, dry_run))
        return True

    monkeypatch.setattr(runner, "_run_up_migration", _run_up)

    success = await runner._run_pending_migrations(
        mongo_db=MagicMock(),
        pg_session=AsyncMock(),
        dry_run=True,
        yes=False,
    )

    assert success is True
    assert calls == [("002", "second", True)]


@pytest.mark.asyncio
async def test_run_pending_migrations_no_pending(monkeypatch):
    async def _applied_versions(_session):
        return {"001_first"}

    monkeypatch.setattr(runner, "_get_applied_versions", _applied_versions)
    monkeypatch.setattr(runner, "_discover_migrations", lambda: [("001", "first")])

    run_up = AsyncMock(return_value=True)
    monkeypatch.setattr(runner, "_run_up_migration", run_up)

    success = await runner._run_pending_migrations(
        mongo_db=MagicMock(),
        pg_session=AsyncMock(),
        dry_run=False,
        yes=True,
    )

    assert success is True
    run_up.assert_not_awaited()
