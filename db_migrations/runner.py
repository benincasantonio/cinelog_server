"""Runner for PostgreSQL-backed data migrations.

This runner discovers ``mNNN_*`` modules in ``db_migrations/`` and
applies only versions that have not yet been recorded in PostgreSQL.

Usage:
    python -m db_migrations.runner [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import os
import re
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.postgres import get_database_url

VERSIONS_TABLE = "data_migration_versions"
CREATE_VERSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS data_migration_versions (
    migration_id TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL
)
"""
SELECT_APPLIED_MIGRATIONS_SQL = "SELECT migration_id FROM data_migration_versions"
INSERT_APPLIED_MIGRATION_SQL = """
INSERT INTO data_migration_versions (migration_id, applied_at)
VALUES (:migration_id, :applied_at)
ON CONFLICT (migration_id) DO NOTHING
"""


def _get_mongodb_settings() -> tuple[str, str]:
    """Get MongoDB connection settings from environment variables."""
    mongodb_uri = os.getenv("MONGODB_URI")

    if mongodb_uri:
        parsed = urllib.parse.urlparse(mongodb_uri)
        db_name_from_uri = parsed.path.lstrip("/") if parsed.path else None

        if db_name_from_uri:
            return mongodb_uri, db_name_from_uri

        mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")
        return mongodb_uri, mongodb_db

    mongodb_host = os.getenv("MONGODB_HOST", "localhost")
    mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
    mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")

    return f"mongodb://{mongodb_host}:{mongodb_port}/?directConnection=true", mongodb_db


def _migration_id(version: str, module_name: str) -> str:
    """Build a migration identifier from version + module name."""
    return f"{version}_{module_name}"


def _discover_migrations() -> list[tuple[str, str]]:
    """Discover migration files in the ``db_migrations`` directory."""
    migrations_dir = Path(__file__).resolve().parent
    if not migrations_dir.exists():
        return []

    pattern = re.compile(r"^m(\d{3})_(.+)\.py$")
    migrations: list[tuple[str, str]] = []

    for filename in os.listdir(migrations_dir):
        match = pattern.match(filename)
        if not match or filename == "__init__.py":
            continue

        version = match.group(1)
        module_name = match.group(2)
        migrations.append((version, module_name))

    migrations.sort(key=lambda x: x[0])
    return migrations


def _get_pending_migrations(
    applied_versions: set[str], discovered_migrations: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Return migrations that are discovered but not yet applied."""
    return [(v, n) for v, n in discovered_migrations if _migration_id(v, n) not in applied_versions]


def _load_migration_module(version: str, module_name: str) -> Any:
    """Load a migration module dynamically."""
    module_path = f"db_migrations.m{version}_{module_name}"
    return importlib.import_module(module_path)


async def _ensure_versions_table(pg_session: AsyncSession) -> None:
    """Create data-migration versions table if it does not exist."""
    await pg_session.execute(text(CREATE_VERSIONS_TABLE_SQL))
    await pg_session.commit()


async def _get_applied_versions(pg_session: AsyncSession) -> set[str]:
    """Read applied migration identifiers from PostgreSQL."""
    table_exists_result = await pg_session.execute(text(f"SELECT to_regclass('public.{VERSIONS_TABLE}')"))
    table_name = table_exists_result.scalar_one_or_none()
    if table_name is None:
        return set()

    result = await pg_session.execute(text(SELECT_APPLIED_MIGRATIONS_SQL))
    migration_ids = result.scalars().all()
    return {str(migration_id) for migration_id in migration_ids}


async def _record_migration(pg_session: AsyncSession, version: str, module_name: str) -> None:
    """Persist a migration as applied in PostgreSQL."""
    await _ensure_versions_table(pg_session)
    await pg_session.execute(
        text(INSERT_APPLIED_MIGRATION_SQL),
        {
            "migration_id": _migration_id(version, module_name),
            "applied_at": datetime.now(UTC),
        },
    )
    await pg_session.commit()


async def _run_up_migration(
    mongo_db: Database,
    pg_session: AsyncSession,
    version: str,
    module_name: str,
    dry_run: bool = False,
) -> bool:
    """Run ``up(...)`` for one data migration."""
    migration_name = _migration_id(version, module_name)
    print(f"[db-migrate] Applying migration: {migration_name}")

    module = _load_migration_module(version, module_name)
    if not hasattr(module, "up"):
        print(f"  [error] Migration {migration_name} does not define up()")
        return False

    up_fn = module.up
    try:
        result = up_fn(mongo_db, pg_session, dry_run=dry_run)
        if inspect.isawaitable(result):
            await result

        if not dry_run:
            await _record_migration(pg_session, version, module_name)

        print(f"  [success] Migration {migration_name} applied")
        return True
    except Exception as exc:
        print(f"  [error] Migration {migration_name} failed: {exc}")
        return False


async def _run_pending_migrations(
    mongo_db: Database,
    pg_session: AsyncSession,
    dry_run: bool = False,
    yes: bool = False,
) -> bool:
    """Discover and run all pending data migrations in order."""
    applied_versions = await _get_applied_versions(pg_session)
    discovered = _discover_migrations()
    pending = _get_pending_migrations(applied_versions, discovered)

    if not pending:
        print("[db-migrate] No pending migrations")
        return True

    print(f"[db-migrate] Found {len(pending)} pending migration(s):")
    for version, module_name in pending:
        print(f"  - {_migration_id(version, module_name)}")

    if not yes and not dry_run:
        response = input("[db-migrate] Apply these migrations? (y/N): ")
        if response.lower() != "y":
            print("[db-migrate] Aborted")
            return False

    for version, module_name in pending:
        if not await _run_up_migration(
            mongo_db,
            pg_session,
            version,
            module_name,
            dry_run=dry_run,
        ):
            return False

    if dry_run:
        print("[db-migrate] Dry run complete (no changes made)")
    else:
        print("[db-migrate] All pending migrations applied successfully")

    return True


async def _run() -> int:
    """Run data migration CLI asynchronously."""
    parser = argparse.ArgumentParser(description="Run PostgreSQL data migrations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending data migrations without applying them",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")

    args = parser.parse_args()

    database_url = get_database_url(required=True)
    mongo_uri, mongo_db_name = _get_mongodb_settings()

    mongo_client: MongoClient | None = None
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        mongo_client = MongoClient(mongo_uri)
        mongo_db = mongo_client[mongo_db_name]

        print(f"[db-migrate] Connected to MongoDB: {mongo_db_name}")

        async with session_factory() as pg_session:
            success = await _run_pending_migrations(
                mongo_db,
                pg_session,
                dry_run=args.dry_run,
                yes=args.yes,
            )

        return 0 if success else 1
    except Exception as exc:
        print(f"[db-migrate] Failed: {exc}")
        return 1
    finally:
        if mongo_client is not None:
            try:
                mongo_client.close()
            except Exception as exc:
                print(f"[db-migrate] Warning: failed to close MongoDB client: {exc}")

        await engine.dispose()


def main() -> int:
    """Synchronous entrypoint for ``python -m db_migrations.runner``."""
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
