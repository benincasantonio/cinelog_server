# PostgreSQL Migration Setup

## Scope

The current setup includes:

- SQLAlchemy asyncio, asyncpg, and Alembic dependencies
- Async PostgreSQL engine/session helpers in `app/db/postgres.py`
- Optional application startup initialization driven by `DATABASE_URL`
- Async Alembic scaffolding and schema migrations
- Local and e2e Docker Compose PostgreSQL services
- Deterministic Mongo ObjectId to PostgreSQL UUID conversion

## Environment

Set `DATABASE_URL` when you want the app or Alembic to initialize PostgreSQL:

```bash
DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5432/cinelog_db
```

Repository activation is controlled through `DB_BACKEND`:

```bash
DB_BACKEND=mongo      # default during mixed-mode migration
# DB_BACKEND=postgres # reserved for later cutover stages
```

If `DB_BACKEND=postgres` is set while repository dependencies are still unsafe for mixed mode, the app fails fast with a clear activation error.

## Local Services

The local Docker stack includes PostgreSQL:

```bash
make docker-up
```

Local connection details:

| Field | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `cinelog_db` |
| User | `cinelog` |
| Password | `cinelog` |

The e2e compose file also includes PostgreSQL on host port `5433` with database `cinelog_e2e_db`.

## Schema Migrations

Run migrations:

```bash
make db-schema-migrate
```

Preview schema migration SQL without applying changes:

```bash
make db-schema-migrate-dry-run
```

Roll back the latest migration:

```bash
make db-schema-rollback
```

Run pending PostgreSQL data migrations:

```bash
make db-data-migrate
```

Preview pending PostgreSQL data migrations:

```bash
make db-data-migrate-dry-run
```

The movie data migration dry-run checks current PostgreSQL `tmdb_id` conflicts, so its inserted/skipped totals match a real run.

Run all pending migration systems (Mongo custom runner + Alembic schema + PostgreSQL data):

```bash
make migrate-all
```

## Deterministic IDs

During migration, PostgreSQL IDs derived from MongoDB documents must use the shared helper:

```python
from app.utils.id_utils import mongo_id_to_uuid

postgres_id = mongo_id_to_uuid("507f1f77bcf86cd799439011")
```

The helper uses UUID's built-in `NAMESPACE_URL` namespace and maps only the Mongo ObjectId value. The same Mongo ObjectId always produces the same UUID.

## Movie Collection Migration

`#126` introduces the first repository/data migration for movies.

### Repository split

- Legacy Mongo implementation lives in `app/repository/movie_repository.py` as `MovieRepository` (deprecated during migration).
- New PostgreSQL implementation lives in `app/repository/postgres_movie_repository.py` as `PostgresMovieRepository`. It is prepared but intentionally not wired into dependency injection — see [Activation Guardrails](#activation-guardrails).

### Table shape

Alembic migration creates `movies` with canonical fields (`title`, `release_date`, `runtime`, etc.) plus provider cache fields:

- `tmdb_payload JSONB NULL`
- `tmdb_last_synced_at TIMESTAMPTZ NULL`

### Data migration script

Use `db_migrations/m001_migrate_movies.py` with async session wiring:

- `up(mongo_db, pg_session, dry_run=False)` migrates active (non-deleted) movies
- `down(mongo_db, pg_session)` clears the PostgreSQL movies table

Migration rules:

- Skip `deleted=True` Mongo rows
- Map Mongo `_id` -> Postgres UUID via `mongo_id_to_uuid(...)`
- Idempotent inserts by `tmdb_id` uniqueness
- Progress reporting (total / inserted / skipped)

## User Collection Migration

`#127` adds PostgreSQL user persistence and data migration scaffolding while keeping Mongo active at runtime.

### Repository split

- Legacy Mongo implementation remains in `app/repository/user_repository.py` as `UserRepository` (deprecated during migration).
- New PostgreSQL implementation lives in `app/repository/postgres_user_repository.py` as `PostgresUserRepository`.
- Runtime activation is intentionally blocked by `get_user_repository()` until the user-ID cutover is safe.

### Table shape

Alembic migration creates `users` with canonical account/profile fields and soft-delete metadata:

- `email TEXT NOT NULL`
- `handle TEXT NOT NULL`
- `first_name`, `last_name`, `bio`, `profile_visibility`
- `date_of_birth DATE NULL`
- `password_hash`, `reset_password_code`, `reset_password_expires`

Case-insensitive email uniqueness is enforced with a functional unique index:

- `CREATE UNIQUE INDEX uq_users_email_lower ON users (LOWER(email))`

Case-insensitive handle uniqueness is also enforced while preserving the user's chosen casing:

- `CREATE UNIQUE INDEX uq_users_handle_lower ON users (LOWER(handle))`

### GDPR oblivion behavior

The PostgreSQL user repository mirrors the Mongo oblivion workflow by overwriting or clearing sensitive fields before soft deletion:

- `first_name -> "Deleted"`
- `last_name -> "User"`
- `email -> deleted_<uuid>@deleted.local`
- `handle -> deleted_<uuid>`
- `bio`, `password_hash`, `reset_password_code`, `reset_password_expires`, `date_of_birth` -> `NULL`
- `deleted = TRUE`, `deleted_at = now()`

### Data migration script

Use `db_migrations/m002_migrate_users.py` with async session wiring:

- `up(mongo_db, pg_session, dry_run=False)` migrates active (non-deleted) users
- `down(mongo_db, pg_session)` deletes only PostgreSQL rows whose UUIDs derive from the current Mongo `users` collection

Migration rules:

- Skip `deleted=True` Mongo rows
- Map Mongo `_id` -> Postgres UUID via `mongo_id_to_uuid(...)`
- Normalize Mongo `dateOfBirth` into SQL `DATE`
- Preserve password-reset fields, profile visibility, and timestamps
- Idempotent inserts via PostgreSQL `ON CONFLICT DO NOTHING`
- Progress reporting (total / inserted / skipped)

## Activation Guardrails

PostgreSQL movie activation is intentionally blocked in mixed mode while `LogRepository` and `MovieRatingRepository` still persist/query Mongo ObjectId movie references.

Activation must happen through dependency wiring (`app/dependencies/repository_dependency.py`), not controller imports.

PostgreSQL user activation is also intentionally blocked in mixed mode while JWT subjects, `auth_dependency`, ownership checks, Redis cache keys, and still-active Mongo repositories depend on ObjectId user references.

JWT `sub` values and public response IDs remain Mongo ObjectId strings until the core cutover is complete.

## Later Tickets

Future migration tickets should add:

- User/movie_rating/log PostgreSQL repository migrations
- Safe full backend cutover once ID dependencies are resolved
- Final MongoDB decommissioning
