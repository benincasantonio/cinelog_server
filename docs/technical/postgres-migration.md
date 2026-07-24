# PostgreSQL Migration

## Status: Migration Complete ✅

The MongoDB → PostgreSQL migration is finished. All four repositories (movies, users, movie ratings, logs) run on PostgreSQL in production, the data migration scripts have been executed and verified, and MongoDB has been removed from the codebase entirely.

**What was removed in the final cleanup (issue #130):**

- `beanie` runtime dependency and `mongomock-motor` dev dependency
- Beanie document models (`app/models/base_entity.py`, `user.py`, `movie.py`, `log.py`, `movie_rating.py`)
- Mongo repositories (`app/repository/user_repository.py`, `movie_repository.py`, `log_repository.py`, `movie_rating_repository.py`)
- The `DB_BACKEND` feature flag and `is_postgres_required()` backend switching
- MongoDB migration runner (`migrations/`) and Mongo→Postgres data migration scripts (`db_migrations/`)
- MongoDB services in all Docker Compose files and the `migrate.yml` GitHub workflow
- `MONGODB_*` environment variables
- `mongo_id_to_uuid()` / `to_object_id()` ID conversion helpers

`LogCacheRepository` was ported to UUID/PostgreSQL and now always wraps the log repository, restoring Redis log caching.

**Post-migration rename (issue #181):** the `Postgres*` prefixes used during the mixed-mode window were dropped once Mongo was gone. The current canonical names are `UserRepository`, `MovieRepository`, `MovieRatingRepository`, `LogRepository` (in `app/repository/{user,movie,movie_rating,log}_repository.py`) and the models `User`, `Movie`, `MovieRating`, `Log`, `BaseEntity` (files keep the `_model.py` suffix). The historical sections below intentionally keep the old `Postgres*` names as a record of the migration period.

Phases (all completed):

- [x] #125 — Postgres infrastructure setup
- [x] #126 — Movie repository → PostgreSQL
- [x] #127 — User repository → PostgreSQL
- [x] #128 — MovieRating repository → PostgreSQL
- [x] #129 — Log repository → PostgreSQL
- [x] #130 — Remove MongoDB completely

The sections below document the current PostgreSQL setup; the per-collection migration sections are kept as a historical record of how the data was moved.

## Environment

`DATABASE_URL` is required for the app and Alembic:

```bash
DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5432/cinelog_db
```

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

Alembic is the only migration system. The Mongo→Postgres data migration targets (`db-data-migrate`, `migrate-all`, `postgres-migrate-all`, and their dry-run variants) were removed with the migration tooling once the production data migration completed.

### Alembic migration test harness

Migration tests use the shared `alembic_test_harness` pytest fixture from `tests/units/db/conftest.py`. The fixture provisions a unique PostgreSQL database with `pytest-postgresql`, points Alembic at that database, and removes it after the test.

The `AlembicTestHarness` interface provides:

- `upgrade(revision="head")` to run real Alembic upgrades
- `downgrade(revision)` to test rollback behavior
- `connect()` to seed legacy rows and inspect data or constraints with direct SQL

A migration test should upgrade to the preceding revision, seed the old database shape, upgrade to the revision under test, and verify both data and schema behavior. Reversible migrations should also be downgraded and verified. Tests using this fixture remain part of `make test-unit` because they live under `tests/units/`.

## Production Compose Migration

`docker-compose.prod.yml` includes a one-shot `db-migrate` service that runs before the API starts:

```bash
alembic upgrade head
```

The API service depends on `db-migrate` with `service_completed_successfully`, so a failed schema migration prevents the API container from starting.

Required production Compose settings:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | External PostgreSQL database URL, required |
| `JWT_SECRET_KEY` | API auth signing secret |
| `RATE_LIMIT_HMAC_SECRET` | HMAC secret for account-based rate-limit identifiers |
| `REGISTRATION_VERIFICATION_HMAC_SECRET` | HMAC secret for registration verification codes and keys |
| `CURSOR_PAGINATION_HMAC_SECRET` | Dedicated HMAC secret for opaque pagination cursors |
| `TMDB_API_KEY` | TMDB API key |

Start production Compose after the required variables are present in the host environment or `.env`:

```bash
make docker-prod-up
```

The `db-migrate` service is idempotent: Alembic skips already-applied schema revisions.

### Reaching a managed PostgreSQL on an external Docker network

Some managed PostgreSQL setups expose the database only through an internal container hostname (for example `dddkln2s1wv5ouou7sobil35ob4`) that is **resolvable solely on the platform's shared Docker network**. Running the prod stack on its own isolated bridge network then causes the migration to fail with:

```
socket.gaierror: [Errno -3] Temporary failure in name resolution
```

`docker-compose.prod.yml` therefore attaches the `db-migrate` and `api` services to an external network (while keeping `redis` reachable on `default`). Confirm the network name on the host before deploying and update the `networks:` block to match it:

```bash
docker network ls
```

If the declared external network does not exist on the host, Compose fails with `network <name> declared as external, but could not be found`.

Because the `api` service then sits on both the project network and the shared external network, bare service hostnames can collide with other containers on the shared network. The bundled cache is therefore named `cinelog-redis` (not `redis`) so it can never resolve to an unrelated, password-protected Redis on the shared network. Keep `REDIS_URL` pointed at this project-unique hostname.

Alternatively, if the database can be exposed publicly, set `DATABASE_URL` to its public connection string. This avoids the shared network but exposes the database to the internet, so protect it with the host firewall and a strong password.

## Deterministic IDs (historical)

During migration, PostgreSQL IDs derived from MongoDB documents used a shared `mongo_id_to_uuid()` helper based on UUIDv5 with the built-in `NAMESPACE_URL` namespace, so the same Mongo ObjectId always produced the same UUID. The helper was removed with the rest of the Mongo code once the data migration completed; migrated rows keep their derived UUIDs, and new rows use `gen_random_uuid()`.

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

The migration initially preserved the Mongo aggregation shape in `LogRepository`, including a distinct movie-ID handoff to separate movie and rating queries.

After MongoDB removal, issue #191 replaced that compatibility flow with a dedicated SQL-only `StatsRepository`. The current implementation aggregates logs, movie runtime, ratings, and viewing-method distribution in one PostgreSQL statement. See [Statistics Query Implementation](stats-query.md).

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

## Activation Guardrails (historical)

During the mixed-mode migration window, repository activation was gated behind a `DB_BACKEND` flag with fail-fast guards that blocked premature cutover while ObjectId references were still in play. With the cutover complete, the flag and guards were removed: the dependency providers in `app/dependencies/repository_dependency.py` return the PostgreSQL repositories unconditionally, `auth_dependency` returns UUIDs, and stale pre-cutover tokens with ObjectId subjects are rejected with 401.
