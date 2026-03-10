"""Migration runner for Cinelog database migrations.

This module provides a CLI tool to discover and run database migrations.
Migrations are numbered Python files in the migrations/ directory.

Usage:
    python -m migrations.runner [--dry-run] [--yes] [--rollback <version>]
"""

import argparse
import importlib
import os
import re
import sys
import urllib.parse
from datetime import datetime, UTC
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database


def _get_mongodb_settings() -> tuple[str, str]:
    """Get MongoDB connection settings from environment variables.

    Returns:
        Tuple of (mongodb_uri, mongodb_db_name)
    """
    mongodb_uri = os.getenv("MONGODB_URI")

    if mongodb_uri:
        # Parse the database name from the URI path
        parsed = urllib.parse.urlparse(mongodb_uri)
        db_name_from_uri = parsed.path.lstrip("/") if parsed.path else None

        if db_name_from_uri:
            return mongodb_uri, db_name_from_uri

        # If no DB name in URI, fall back to MONGODB_DB env var
        mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")
        return mongodb_uri, mongodb_db

    # Fallback: Use MONGODB_HOST/MONGODB_PORT/MONGODB_DB
    mongodb_host = os.getenv("MONGODB_HOST", "localhost")
    mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
    mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")

    return f"mongodb://{mongodb_host}:{mongodb_port}", mongodb_db


def _get_applied_versions(db: Database) -> set[str]:
    """Get set of migration versions that have already been applied.

    Args:
        db: MongoDB database instance

    Returns:
        Set of migration version strings (e.g., {"001_movie_ids_to_objectid"})
    """
    versions = db.migration_versions.find({}, {"_id": 1})
    return {doc["_id"] for doc in versions}


def _discover_migrations() -> list[tuple[str, str]]:
    """Discover migration files in the migrations/ directory.

    Returns:
        List of (version, module_name) tuples sorted by version number
    """
    migrations_dir = os.path.dirname(__file__)

    if not os.path.exists(migrations_dir):
        return []

    pattern = re.compile(r"^(\d{3})_(.+)\.py$")
    migrations = []

    for filename in os.listdir(migrations_dir):
        match = pattern.match(filename)
        if match and filename != "__init__.py":
            version = match.group(1)
            module_name = match.group(2)
            migrations.append((version, module_name))

    migrations.sort(key=lambda x: x[0])
    return migrations


def _load_migration_module(version: str, module_name: str) -> Any:
    """Load a migration module dynamically.

    Args:
        version: Migration version number (e.g., "001")
        module_name: Migration module name (e.g., "movie_ids_to_objectid")

    Returns:
        Loaded migration module
    """
    module_path = f"migrations.{version}_{module_name}"
    return importlib.import_module(module_path)


def _record_migration(db: Database, version: str, module_name: str) -> None:
    """Record a migration as applied in the migration_versions collection.

    Args:
        db: MongoDB database instance
        version: Migration version to record (e.g., "001")
        module_name: Migration module name (e.g., "movie_ids_to_objectid")
    """
    db.migration_versions.insert_one(
        {
            "_id": f"{version}_{module_name}",
            "applied_at": datetime.now(UTC),
        }
    )


def _remove_migration_record(db: Database, version: str, module_name: str) -> None:
    """Remove a migration record from the migration_versions collection.

    Args:
        db: MongoDB database instance
        version: Migration version to remove (e.g., "001")
        module_name: Migration module name (e.g., "movie_ids_to_objectid")
    """
    db.migration_versions.delete_one({"_id": f"{version}_{module_name}"})


def _run_up_migration(
    db: Database, version: str, module_name: str, dry_run: bool = False
) -> bool:
    """Run the up() function of a migration.

    Args:
        db: MongoDB database instance
        version: Migration version
        module_name: Migration module name
        dry_run: If True, only print what would be done without applying

    Returns:
        True if migration was applied or would be applied, False otherwise
    """
    print(f"[migrate] Applying migration: {version}_{module_name}")

    module = _load_migration_module(version, module_name)

    if not hasattr(module, "up"):
        print(
            f"  [error] Migration {version}_{module_name} does not define up() function"
        )
        return False

    try:
        module.up(db, dry_run=dry_run)
        if not dry_run:
            _record_migration(db, version, module_name)
        print(f"  [success] Migration {version}_{module_name} applied")
        return True
    except Exception as e:
        print(f"  [error] Migration {version}_{module_name} failed: {e}")
        return False


def _run_down_migration(
    db: Database, version: str, module_name: str, dry_run: bool = False
) -> bool:
    """Run the down() function of a migration.

    Args:
        db: MongoDB database instance
        version: Migration version
        module_name: Migration module name
        dry_run: If True, only print what would be done without applying

    Returns:
        True if migration was rolled back or would be rolled back, False otherwise
    """
    print(f"[rollback] Rolling back migration: {version}_{module_name}")

    if dry_run:
        print(f"  [dry-run] Would call {module_name}.down(db)")
        _remove_migration_record(db, version, module_name)
        return True

    module = _load_migration_module(version, module_name)

    if not hasattr(module, "down"):
        print(
            f"  [error] Migration {version}_{module_name} does not define down() function"
        )
        return False

    try:
        module.down(db)
        _remove_migration_record(db, version, module_name)
        print(f"  [success] Migration {version}_{module_name} rolled back")
        return True
    except Exception as e:
        print(f"  [error] Rollback of {version}_{module_name} failed: {e}")
        return False


def _run_pending_migrations(
    db: Database, dry_run: bool = False, yes: bool = False
) -> bool:
    """Discover and run all pending migrations in order.

    Args:
        db: MongoDB database instance
        dry_run: If True, only print what would be done without applying
        yes: If True, skip confirmation prompts

    Returns:
        True if all migrations were applied (or would be applied), False if any failed
    """
    applied_versions = _get_applied_versions(db)
    discovered = _discover_migrations()

    pending = [
        (v, n) for v, n in discovered if f"{v}_{n}" not in applied_versions
    ]

    if not pending:
        print("[migrate] No pending migrations")
        return True

    print(f"[migrate] Found {len(pending)} pending migration(s):")
    for version, module_name in pending:
        print(f"  - {version}_{module_name}")

    if not yes and not dry_run:
        response = input("[migrate] Apply these migrations? (y/N): ")
        if response.lower() != "y":
            print("[migrate] Aborted")
            return False

    for version, module_name in pending:
        if not _run_up_migration(db, version, module_name, dry_run=dry_run):
            return False

    if not dry_run:
        print("[migrate] All migrations applied successfully")
    else:
        print("[dry-run] Migration plan complete (no changes made)")

    return True


def _rollback_migration(
    db: Database, target_version: str, dry_run: bool = False, yes: bool = False
) -> bool:
    """Rollback a specific migration.

    Args:
        db: MongoDB database instance
        target_version: Migration version to rollback (e.g., "001")
        dry_run: If True, only print what would be done without applying
        yes: If True, skip confirmation prompts

    Returns:
        True if rollback succeeded (or would succeed), False otherwise
    """
    applied_versions = _get_applied_versions(db)

    discovered = _discover_migrations()
    version_map = {v: n for v, n in discovered}

    if target_version not in version_map:
        print(f"[rollback] Migration {target_version} not found")
        return False

    module_name = version_map[target_version]
    migration_id = f"{target_version}_{module_name}"

    if migration_id not in applied_versions:
        print(f"[rollback] Migration {target_version} is not applied")
        return False

    if not yes and not dry_run:
        response = input(
            f"[rollback] Rollback migration {target_version}_{module_name}? (y/N): "
        )
        if response.lower() != "y":
            print("[rollback] Aborted")
            return False

    return _run_down_migration(db, target_version, module_name, dry_run=dry_run)


def main() -> int:
    """Main entry point for the migration runner.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    parser = argparse.ArgumentParser(description="Run Cinelog database migrations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without applying them",
    )
    parser.add_argument(
        "--yes", action="store_true", help="Skip confirmation prompts (for CI/CD)"
    )
    parser.add_argument(
        "--rollback",
        metavar="VERSION",
        help="Rollback a specific migration (e.g., 001)",
    )

    args = parser.parse_args()

    mongodb_uri, mongodb_db_name = _get_mongodb_settings()

    client: MongoClient | None = None
    try:
        client = MongoClient(mongodb_uri, directConnection=True)
        db = client[mongodb_db_name]

        print(f"[migrate] Connected to MongoDB: {mongodb_db_name}")

        if args.rollback:
            success = _rollback_migration(
                db, args.rollback, dry_run=args.dry_run, yes=args.yes
            )
        else:
            success = _run_pending_migrations(db, dry_run=args.dry_run, yes=args.yes)

        return 0 if success else 1
    except Exception as e:
        print(f"[error] Migration failed: {e}")
        return 1
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
