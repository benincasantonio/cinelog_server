# Database Migrations

This guide covers the Cinelog database migration system — a lightweight, versioned migration framework for MongoDB.

## Overview

The migration system is a custom Python-based solution that uses PyMongo (sync) to discover and run numbered migration scripts. It tracks applied migrations in the `migration_versions` collection and supports dry-run mode for impact preview before execution.

**Key characteristics:**

- **Lightweight** — No external migration library (Alembic, etc.), just Python scripts
- **Versioned** — Migrations numbered `001`, `002`, `003`, etc., run in order
- **Idempotent** — Won't re-run migrations that are already applied
- **Dry-run** — Preview impact (affected document counts) without making changes
- **CI/CD ready** — `--yes` flag for non-interactive automation

## Usage

### Local Development

Run pending migrations with confirmation prompt:

```bash
make migrate
# or
uv run python -m migrations.runner
```

Preview what would be changed:

```bash
make migrate-dry-run
# or
uv run python -m migrations.runner --dry-run
```

### CI/CD

Run migrations without prompts (for GitHub Actions, deployment scripts, etc.):

```bash
uv run python -m migrations.runner --yes
```

### Rollback

Rollback a specific migration:

```bash
uv run python -m migrations.runner --rollback 001
```

**Note:** Not all migrations support rollback — check the migration's `down()` function.

## How It Works

### Discovery

The runner scans the `migrations/` directory for files matching the pattern `NNN_name.py`, where `NNN` is a 3-digit number. Example:

```
migrations/
  __init__.py
  runner.py
  001_movie_ids_to_objectid.py
  002_add_some_feature.py
  003_another_change.py
```

### Version Tracking

Applied migrations are recorded in the `migration_versions` collection:

```json
{
  "_id": "001_movie_ids_to_objectid",
  "applied_at": ISODate("2026-03-06T21:47:00Z")
}
```

When you run the runner, it compares the `migration_versions` collection with discovered files to determine which are pending.

### Execution Flow

1. Connect to MongoDB using `MONGODB_URI` (preferred) or `MONGODB_HOST`/`MONGODB_PORT`/`MONGODB_DB`
2. Scan `migration_versions` for applied versions
3. Discover migration files in `migrations/`, sort numerically
4. For each pending migration:
   - Call its `up(db)` function, passing a sync PyMongo `Database` object
   - On success, record the version in `migration_versions`
   - On failure, abort and exit with code 1 (failed migration is not recorded)

## Dry-Run Mode

The `--dry-run` flag executes the migration's `up(db, dry_run=True)` function, which:

- **Queries the real MongoDB** to get accurate impact counts
- **Prints details** (affected documents, collections, preview of IDs)
- **Makes zero writes** — no documents are inserted, updated, or deleted

Example dry-run output:

```
[migrate] Found 1 pending migration(s):
  - 001_movie_ids_to_objectid
  [001] Converting movies._id from string to ObjectId...
    [001] Found 2 movie(s) with string _id
    [dry-run] Would convert movie IDs:
      - 69a86e802887d42358b9b1aa -> ObjectId('69a86e802887d42358b9b1aa')
      - 69a86ed92887d42358b9b1ad -> ObjectId('69a86ed92887d42358b9b1ad')
  [001] Converting logs.movieId from string to ObjectId...
    [001] No logs with string movieId found
[dry-run] Migration plan complete (no changes made)
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview migrations without applying changes |
| `--yes` | Skip confirmation prompts (for CI/CD) |
| `--rollback VERSION` | Rollback a specific migration (e.g., `001`) |
| `-h, --help` | Show help message |

## Writing a New Migration

### File Naming

Create a new file in `migrations/` with a 3-digit prefix and descriptive name:

```
migrations/002_add_user_email_verified.py
```

### Required Functions

Each migration module must define two functions:

```python
from pymongo.database import Database

def up(db: Database, dry_run: bool = False) -> None:
    """Apply the migration.

    Args:
        db: PyMongo Database instance (sync)
        dry_run: If True, report impact but don't apply changes
    """
    pass

def down(db: Database) -> None:
    """Rollback the migration.

    Args:
        db: PyMongo Database instance (sync)
    """
    pass
```

### Example Migration Template

```python
"""Migration 002: Add email verification field to users.

This migration adds a new `emailVerified` boolean field to all user documents.
"""
from pymongo.database import Database


def up(db: Database, dry_run: bool = False) -> None:
    """Add emailVerified field with default False."""
    users_collection = db.users

    if dry_run:
        count = users_collection.count_documents(
            {"emailVerified": {"$exists": False}}
        )
        print("  [002] Would update {} user(s)".format(count))
        return

    result = users_collection.update_many(
        {"emailVerified": {"$exists": False}},
        {"$set": {"emailVerified": False}}
    )
    print("  [002] Updated {} user(s)".format(result.modified_count))


def down(db: Database) -> None:
    """Remove emailVerified field."""
    users_collection = db.users

    result = users_collection.update_many(
        {},
        {"$unset": {"emailVerified": 1}}
    )
    print("  [002] Removed emailVerified from {} user(s)".format(result.modified_count))
```

### Best Practices

1. **Always support dry_run** — The `up(db, dry_run=False)` parameter should be used to preview changes without executing writes. Check `dry_run` early and return after reporting impact.

2. **Use descriptive logging** — Print what's happening with `[NNN]` prefix so it's clear which migration is reporting.

3. **Be idempotent** — A migration should handle being run on an already-migrated dataset (check if changes exist first).

4. **Atomic when possible** — Use bulk operations (`update_many`, `insert_many`) instead of loops for better performance and atomicity.

5. **Document the purpose** — Include a module docstring explaining what the migration does and why.

6. **Test dry_run** — The dry-run mode should use the same queries as the actual migration, just without writes.

## CI/CD Integration

The migration system integrates with GitHub Actions via `.github/workflows/migrate.yml`.

### Required Secrets

Configure this in your GitHub repository settings:

| Secret | Description | Example |
|--------|-------------|---------|
| `MONGODB_URI` | Full MongoDB connection string (DB name should be in the URI path) | `mongodb+srv://user:pass@cluster.example.net/cinelog_db` |

### Workflow Features

- **Manual trigger** — Run via "Actions" tab in GitHub, with optional `dry_run` input
- **Auto-trigger** — Runs on push to `main`/`master` when `migrations/` files change
- **Concurrency control** — Prevents multiple migration runs from overlapping
- **Dry-run support** — Can preview changes before applying in production

### Workflow Usage

1. Go to the "Actions" tab in GitHub
2. Select "Database Migrations"
3. Click "Run workflow"
4. Choose branch and optionally enable dry-run
5. Click "Run workflow"

## Example: Migration 001

The first migration, `001_movie_ids_to_objectid`, converts string `_id` values to ObjectId across three collections:

**What it fixes:** Older data had `_id` stored as strings instead of proper ObjectIds.

**Collections affected:**

- `movies._id` — Convert from string to ObjectId (same hex value)
- `logs.movieId` — Convert FK references from string to ObjectId
- `movie_ratings.movieId` — Convert FK references from string to ObjectId

**Implementation notes:**

- `movies._id` requires delete+reinsert because `_id` is immutable in MongoDB
- The delete+reinsert for `movies._id` is wrapped in a MongoDB transaction for atomicity (to avoid `DuplicateKeyError` on the `tmdbId` unique index)
- `logs.movieId` and `movie_ratings.movieId` use `$toObjectId` aggregation for efficient bulk updates
- Identity is preserved — the string `"507f1f77bcf86cd799439011"` becomes `ObjectId("507f1f77bcf86cd799439011")`

**Run it:**

```bash
# Preview impact
make migrate-dry-run

# Apply
make migrate
```

**Rollback:** Not supported — this is a data type correction that should not be reversed.

## Troubleshooting

### Migration fails mid-run

If a migration fails during execution:

1. The failed migration is **not** recorded in `migration_versions`
2. You can fix the issue and re-run — the runner will retry pending migrations
3. Partially applied changes may need manual cleanup (check the migration's specific behavior)

### No pending migrations shown

If you expect pending migrations but don't see them:

1. Check file naming: must be `NNN_name.py` format (e.g., `001_example.py`)
2. Verify migration files are in the `migrations/` directory
3. Check if migrations are already recorded in `migration_versions` collection

### MongoDB connection fails

The runner uses the same environment variables as the app:

```bash
# Option 1: Full URI (preferred, DB name in path)
export MONGODB_URI="mongodb://localhost:27017/cinelog_db"

# Option 2: Host/port/db separately (fallback for local dev)
export MONGODB_HOST=localhost
export MONGODB_PORT=27017
export MONGODB_DB=cinelog_db
```

Note: When using `MONGODB_URI` with a DB name in the path (e.g., `/cinelog_db`), the runner extracts the DB name from the URI. If no DB name is in the path, it falls back to `MONGODB_DB` env var or the default `cinelog_db`.

**Replica set requirement:** Some migrations (e.g., `001_movie_ids_to_objectid`) use MongoDB transactions, which require a replica set. The local development Docker setup (`docker-compose.local.yml`) configures a single-node replica set (`rs0`) for this reason.

**Direct connection:** When connecting to a single-node replica set, use `directConnection=True` to prevent PyMongo from trying to discover topology via Docker-internal hostnames. The migration runner sets this automatically.

## See Also

- [AGENTS.md](../AGENTS.md) — Development guide and operational reference
- [ARCHITECTURE.md](../ARCHITECTURE.md) — Codebase architecture reference
- [docs/README.md](README.md) — Overview of all documentation
