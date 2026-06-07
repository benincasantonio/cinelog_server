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

Run only the PostgreSQL cutover path, with schema migrations before data migrations:

```bash
make postgres-migrate-all
```

This target is the same migration order used by production Compose.

## Production Compose Migration

`docker-compose.prod.yml` includes a one-shot `db-migrate` service that runs before the API starts:

```bash
alembic upgrade head && python -m db_migrations.runner --yes
```

The production order is intentionally PostgreSQL schema first, then MongoDB-to-PostgreSQL data migrations. The API service depends on `db-migrate` with `service_completed_successfully`, so a failed schema or data migration prevents the API container from starting.

Required production Compose settings:

| Variable | Purpose |
| --- | --- |
| `POSTGRES_DB` | PostgreSQL database name, defaults to `cinelog_db` |
| `POSTGRES_USER` | PostgreSQL user, defaults to `cinelog` |
| `POSTGRES_PASSWORD` | PostgreSQL password, required |
| `MONGODB_URI` | Source MongoDB URI for data migration, required |
| `JWT_SECRET_KEY` | API auth signing secret |
| `RATE_LIMIT_HMAC_SECRET` | HMAC secret for account-based rate-limit identifiers |
| `TMDB_API_KEY` | TMDB API key |

Start production Compose after the required variables are present in the host environment or `.env`:

```bash
make docker-prod-up
```

The `db-migrate` service is idempotent: Alembic skips already-applied schema revisions, and `db_migrations.runner` skips data migrations recorded in `data_migration_versions`.

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

## MovieRating Collection Migration

`#128` adds PostgreSQL movie-rating persistence and migration scaffolding while Mongo remains active at runtime.

### Repository split

- Legacy Mongo implementation remains in `app/repository/movie_rating_repository.py` as `MovieRatingRepository` (deprecated during migration).
- New PostgreSQL implementation lives in `app/repository/postgres_movie_rating_repository.py` as `PostgresMovieRatingRepository`.
- Runtime activation is intentionally blocked by `get_movie_rating_repository()` until user/movie/log ID dependencies are safe.

### Table shape

Alembic migration creates `movie_ratings` with canonical rating fields and soft-delete metadata:

- `user_id UUID NOT NULL REFERENCES users(id)`
- `movie_id UUID NOT NULL REFERENCES movies(id)`
- `tmdb_id INTEGER NOT NULL`
- `rating INTEGER NULL CHECK (rating BETWEEN 1 AND 10)`
- `review TEXT NULL`

The current Mongo uniqueness/upsert identity is preserved with:

- `UNIQUE (user_id, tmdb_id)`

The main read path also gets a supporting composite index:

- `CREATE INDEX ix_movie_ratings_user_movie ON movie_ratings (user_id, movie_id)`

### Native upsert behavior

`PostgresMovieRatingRepository.create_update_movie_rating(...)` uses PostgreSQL `INSERT .. ON CONFLICT .. DO UPDATE` keyed by `(user_id, tmdb_id)` instead of Mongo's application-level check-then-save flow.

Conflict updates:

- overwrite `movie_id`, `rating`, and `review`
- refresh `updated_at`
- clear `deleted` / `deleted_at` so a matching soft-deleted row is revived

### Data migration script

Use `db_migrations/m003_migrate_movie_ratings.py` with async session wiring:

- `up(mongo_db, pg_session, dry_run=False)` migrates active (non-deleted) movie ratings
- `down(mongo_db, pg_session)` deletes only PostgreSQL rows whose UUIDs derive from the current Mongo `movie_ratings` collection

Migration rules:

- Skip `deleted=True` Mongo rows
- Map Mongo `_id`, `userId`, and `movieId` -> Postgres UUID via `mongo_id_to_uuid(...)`
- Validate that derived `user_id` and `movie_id` already exist in PostgreSQL before insert
- Skip missing-FK rows with warnings
- Preserve `tmdbId`, `rating`, `review`, and timestamps
- Idempotent inserts via PostgreSQL `ON CONFLICT (user_id, tmdb_id) DO NOTHING`
- Progress reporting (total / inserted / skipped / warnings)

## Log Collection Migration

`#129` adds PostgreSQL log persistence and migration scaffolding while Mongo remains active at runtime.

### Repository split

- Legacy Mongo implementation remains in `app/repository/log_repository.py` as `LogRepository` (deprecated during migration).
- New PostgreSQL implementation lives in `app/repository/postgres_log_repository.py` as `PostgresLogRepository`.
- Runtime activation is intentionally blocked by `get_log_repository()` until the later runtime cutover work is complete.

### Table shape

Alembic migration creates `logs` with canonical viewing-log fields plus shared lifecycle metadata:

- `user_id UUID NOT NULL REFERENCES users(id)`
- `movie_id UUID NOT NULL REFERENCES movies(id)`
- `tmdb_id INTEGER NOT NULL`
- `date_watched TIMESTAMPTZ NOT NULL`
- `viewing_notes TEXT NULL`
- `poster_path TEXT NULL`
- `watched_where TEXT NOT NULL DEFAULT 'other'`

`watched_where` is constrained to the same application-level choices:

- `cinema`
- `streaming`
- `homeVideo`
- `tv`
- `other`

### Hard-delete parity

Unlike the other migrated repositories, logs preserve their current hard-delete behavior.

- reads still filter with `active()` for parity and safety
- `delete_log(...)` physically deletes the row instead of flipping `deleted=True`

### Stats aggregation port

`PostgresLogRepository.get_log_stats(...)` preserves the current Mongo response shape:

- `total_watches`
- `unique_titles`
- `unique_movie_ids`
- `distribution`

Implementation uses a shared filtered CTE and two PostgreSQL aggregation queries:

- summary query: `COUNT(*)`, `COUNT(DISTINCT movie_id)`, `array_agg(DISTINCT movie_id)`
- distribution query: `GROUP BY watched_where`

`LogStats.unique_movie_ids` is widened during the migration window so it can safely carry Mongo `PydanticObjectId` values today and PostgreSQL UUIDs after cutover.

### Data migration script

Use `db_migrations/m004_migrate_logs.py` with async session wiring:

- `up(mongo_db, pg_session, dry_run=False)` migrates active (non-deleted) logs
- `down(mongo_db, pg_session)` deletes only PostgreSQL rows whose UUIDs derive from the current Mongo `logs` collection

Migration rules:

- Skip `deleted=True` Mongo rows
- Map Mongo `_id`, `userId`, and `movieId` -> Postgres UUID via `mongo_id_to_uuid(...)`
- Validate that derived `user_id` and `movie_id` already exist in PostgreSQL before insert
- Normalize invalid or missing `dateWatched` values into warnings/skips
- Normalize invalid `watchedWhere` values to `other`
- Preserve `tmdbId`, `viewingNotes`, `posterPath`, and timestamps
- Idempotent inserts via PostgreSQL `ON CONFLICT (id) DO NOTHING`
- Progress reporting (total / inserted / skipped / warnings)

## Activation Guardrails

PostgreSQL movie activation is intentionally blocked in mixed mode while `LogRepository` and `MovieRatingRepository` still persist/query Mongo ObjectId movie references.

Activation must happen through dependency wiring (`app/dependencies/repository_dependency.py`), not controller imports.

PostgreSQL user activation is also intentionally blocked in mixed mode while JWT subjects, `auth_dependency`, ownership checks, Redis cache keys, and still-active Mongo repositories depend on ObjectId user references.

PostgreSQL movie-rating activation is intentionally blocked in mixed mode while auth still emits ObjectId user IDs, `LogRepository` still consumes ObjectId movie IDs, and `MovieRepository` cutover remains blocked behind the earlier movie guard.

PostgreSQL log activation is intentionally blocked in mixed mode while `LogCacheRepository`, service wiring, and runtime ID assumptions still require the later cutover work before PostgreSQL logs can safely back live requests.

JWT `sub` values and public response IDs remain Mongo ObjectId strings until the core cutover is complete.

## Later Tickets

Future migration tickets should add:

- Runtime repository cutover and PostgreSQL-safe log caching
- Safe full backend cutover once ID dependencies are resolved
- Final MongoDB decommissioning
