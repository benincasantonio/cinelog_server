# Architecture

This document is the definitive architecture reference for the Cinelog Server codebase.

## Layered Architecture

The codebase follows a clean layered architecture:

1. **Controllers** (`app/controllers/`) — FastAPI route handlers that define API endpoints
2. **Services** (`app/services/`) — Business logic layer that orchestrates repository operations and external integrations
3. **Repositories** (`app/repository/`) — Data access layer using async SQLAlchemy
4. **Models** (`app/models/`) — SQLAlchemy ORM models representing database tables
5. **Schemas** (`app/schemas/`) — Pydantic models for request/response validation
6. **Dependencies** (`app/dependencies/`) — FastAPI dependency injection (e.g., JWT auth)
7. **Middleware** (`app/middleware/`) — Request processing middleware (e.g., CSRF protection)
8. **Config** (`app/config/`) — Application configuration (e.g., CORS)
9. **Utils** (`app/utils/`) — Shared utilities (exceptions, error codes, cookie management, sanitization, datetime, ID validation)
10. **Workers** (`app/workers/`) — Standalone background process entrypoints (process concerns only — signal handling, poll loop, logging setup; delivery logic itself lives in `app/services/`)

## API Versioning

All routes are registered under the `/v1/` prefix:

| Controller | Prefix | Purpose |
|---|---|---|
| `auth_controller` | `/v1/auth` | Registration, login, logout, token refresh, password reset, CSRF |
| `movie_controller` | `/v1/movies` | TMDB movie search and details |
| `log_controller` | `/v1/logs` | Viewing log CRUD |
| `user_controller` | `/v1/users` | User info and user logs |
| `movie_rating_controller` | `/v1/movie-ratings` | Movie rating CRUD |
| `stats_controller` | `/v1/stats` | Viewing statistics |
| `notification_controller` | `/v1/notifications` | Notification inbox and read state |

The outbound-message delivery worker (`app/workers/outbound_message_worker.py`) is a
separate standalone process — it exposes no HTTP routes. See
[Background Workers](#background-workers) below.

## App Initialization

`app/__init__.py` uses a FastAPI lifespan context manager:

**Startup:**
1. Initialize the async SQLAlchemy engine from `DATABASE_URL` (`init_postgres_engine()` in `app/db/postgres.py`)
2. Initialize `CacheService` from Redis config and fail fast if Redis is unreachable

**Shutdown:**
1. Close cache service connections (`CacheService.aclose_all()`)
2. Close TMDB service connections (`TMDBService.aclose_all()`)
3. Dispose the PostgreSQL engine (`close_postgres_engine()`)

**Middleware stack** (in order): RateLimitSessionMiddleware → CSRFMiddleware → CORSMiddleware

**Global exception handler** catches `AppException` and returns structured JSON via `ErrorSchema`.

## Key Patterns

**Dependency Flow:**

- Controllers depend on services via `Depends(get_*_service)` from `app/dependencies/service_dependency.py`
- Each `get_*_service` provider is `@lru_cache`-d and constructs the service with its repositories from `app/dependencies/repository_dependency.py`
- Repositories handle direct database operations through async SQLAlchemy sessions
- `LogCacheRepository` is a composition-based Redis decorator over the log repository and is wired in `get_log_service()` / `get_stats_service()`

**Repository Conventions:**

- Repositories extend `RepositoryBase` (`app/repository/repository_base.py`), which accepts a `session_provider` (defaults to `get_async_session` from `app/db/postgres.py`); tests inject their own provider
- Each repository has a `Protocol` interface in `app/repository/*_repository_protocol.py` that services type-hint against
- Repository methods are instance methods; services should not call repository classes statically
- `RepositoryBase._unit_of_work(session=None)` is the shared transaction seam: an async context manager that opens and commits its own session when `session` is `None` (existing single-repository behavior, unchanged), or joins the caller's session and leaves the commit to the caller when one is passed. `NotificationRepository.create_notification()` and `OutboundMessageRepository.enqueue()` both accept an optional keyword-only `session=`, which is how `NotificationUnitOfWork` (`app/repository/notification_unit_of_work.py`) creates a notification and enqueues its outbound message(s) atomically — see [Outbound Email Delivery](docs/technical/outbound-email-delivery.md)

**Error Handling:**

- Custom `AppException` class with structured `ErrorSchema` objects
- Centralized error codes in `app/utils/error_codes_utils.py`
- Global exception handler in `app/__init__.py` converts `AppException` to JSON responses

**Singleton Pattern:**

- `TMDBService` uses a thread-safe singleton with `Lock()` — lazy initialization on first `get_instance()` call, single global `httpx.AsyncClient`
- `CacheService` uses a thread-safe singleton with `Lock()` — explicit initialization via `initialize(config)` during app startup

**Soft Delete:**

- `BaseEntity.active()` returns a SQLAlchemy criterion (`deleted IS FALSE`) — used by repository queries to exclude soft-deleted records

## Base Entity Pattern

All ORM models inherit from `BaseEntity` (`app/models/base_model.py`), which provides:

- Soft delete support (`deleted`, `deleted_at`)
- Automatic timestamps (`created_at`, `updated_at`) via column defaults and `onupdate`
- `active()` class method returning a soft-delete-aware WHERE criterion

All primary keys are PostgreSQL UUIDs generated by `gen_random_uuid()`.

## Data Models

### User (`users` table — `User`)

| Column | Type | Notes |
|---|---|---|
| `email` | `text` | Unique (case-insensitive index) |
| `handle` | `text` | Unique (case-insensitive index) |
| `first_name`, `last_name` | `text` | |
| `bio` | `text \| null` | |
| `profile_visibility` | `text` | `private` (default) or `public`, CHECK constraint |
| `date_of_birth` | `date \| null` | |
| `password_hash` | `text \| null` | Nullable for legacy accounts |
| `reset_password_code` | `text \| null` | Password reset flow |
| `reset_password_expires` | `timestamptz \| null` | Password reset expiry |

**Indexes:** `uq_users_email_lower` (unique on `lower(email)`), `uq_users_handle_lower` (unique on `lower(handle)`)

### Movie (`movies` table — `Movie`)

| Column | Type | Notes |
|---|---|---|
| `tmdb_id` | `integer` | Unique, indexed — links to TMDB |
| `title` | `text` | |
| `release_date` | `timestamp \| null` | |
| `overview` | `text \| null` | |
| `poster_path` | `text \| null` | |
| `vote_average` | `float \| null` | |
| `runtime` | `integer \| null` | Minutes |
| `original_language` | `text \| null` | |
| `tmdb_payload` | `jsonb \| null` | Raw TMDB response |
| `tmdb_last_synced_at` | `timestamptz \| null` | |

### Log (`logs` table — `Log`)

| Column | Type | Notes |
|---|---|---|
| `user_id` | `uuid` | FK to `users.id` |
| `movie_id` | `uuid` | FK to `movies.id` |
| `tmdb_id` | `integer` | Denormalized TMDB ID |
| `date_watched` | `timestamptz` | |
| `viewing_notes` | `text \| null` | |
| `poster_path` | `text \| null` | Denormalized |
| `watched_where` | `text` | `cinema`, `streaming`, `homeVideo`, `tv`, `other` (CHECK constraint) |

**Indexes:** `(user_id, date_watched DESC)`, `(user_id, date_watched DESC, created_at DESC)`, `(user_id, movie_id)`, `(tmdb_id, date_watched DESC)`, `(user_id, watched_where, created_at)`

### MovieRating (`movie_ratings` table — `MovieRating`)

| Column | Type | Notes |
|---|---|---|
| `user_id` | `uuid` | FK to `users.id` |
| `movie_id` | `uuid` | FK to `movies.id` |
| `tmdb_id` | `integer` | Denormalized |
| `rating` | `integer \| null` | CHECK constraint 1–10 |
| `review` | `text \| null` | |

**Constraints/Indexes:** unique `(user_id, tmdb_id)`, index `(user_id, movie_id)`

### Notification (`notifications` table — `Notification`)

| Column | Type | Notes |
|---|---|---|
| `recipient_id` | `uuid` | Required FK to `users.id` |
| `actor_id` | `uuid \| null` | Optional FK to `users.id` |
| `type` | `text` | Closed `NotificationType` value with CHECK constraint |
| `title`, `body` | `text` | Rendered presentation/history text |
| `deduplication_key` | `text \| null` | Optional per-recipient idempotency key |
| `read_at` | `timestamptz \| null` | Database-owned read timestamp |

**Indexes:** active recipient chronology, active unread recipient chronology, and partial unique `(recipient_id, deduplication_key)` for active non-null keys. Domain resource references belong in typed context tables rather than this common table.

### OutboundMessage (`outbound_messages` table — `OutboundMessage`)

Durable transactional-outbox row for a single channel delivery attempt stream. See [Outbound Email Delivery](docs/technical/outbound-email-delivery.md) for the full state machine, claim protocol, and retry/backoff behavior.

| Column | Type | Notes |
|---|---|---|
| `kind` | `text` | Closed `OutboundMessageKind` value with CHECK constraint (`notification`, `registration_verification`, `registration_existing_account`, `password_reset`) |
| `notification_id` | `uuid \| null` | FK to `notifications.id` ON DELETE CASCADE; required iff `kind = 'notification'` (CHECK constraint) |
| `channel` | `text` | Closed `OutboundMessageChannel` value with CHECK constraint (`email` only, for now) |
| `destination` | `text` | Delivery address, snapshotted at enqueue time |
| `subject`, `text_body`, `html_body` | `text` | Rendered at enqueue; bodies are cleared on terminal status (`delivered` or `failed`) |
| `status` | `text` | Closed `OutboundMessageStatus` value with CHECK constraint, default `pending` |
| `attempt_count` | `integer` | Incremented at claim time, not send time |
| `available_at` | `timestamptz` | Claimable once `now() >= available_at`; also the retry backoff clock |
| `locked_at` | `timestamptz \| null` | Set when claimed, cleared on settle; drives stale-lock recovery |
| `delivered_at` | `timestamptz \| null` | |
| `last_error` | `text \| null` | Sanitized and truncated to 500 characters (CHECK constraint) |

**Constraints/Indexes:** total unique `(notification_id, channel)` (NULLs are distinct, so auth-kind rows repeat freely); partial index `ix_outbound_messages_claimable` on `(channel, available_at, id) WHERE deleted IS FALSE AND status = 'pending'`; partial index `ix_outbound_messages_stale_locks` on `(locked_at) WHERE deleted IS FALSE AND status = 'processing'`. No ORM `relationship()` — the repository joins explicitly.

## Background Workers

`app/workers/outbound_message_worker.py` is a standalone process (`make run-email-worker`, i.e. the root `worker.py` launcher) that repeatedly claims due `outbound_messages` rows with `FOR UPDATE SKIP LOCKED` and delivers them. It never imports `NotificationService` or anything from `app/dependencies/service_dependency.py` — that import chain requires `CURSOR_PAGINATION_HMAC_SECRET`, which the worker has no reason to need, and the worker needs no Redis. It fails fast at startup (`RuntimeError`) if `EmailService.is_configured()` is `False`. See [Outbound Email Delivery](docs/technical/outbound-email-delivery.md) for the full design.

## Authentication Flow

Cookie-based JWT authentication with CSRF double-submit protection. User IDs are UUIDs.

### Login (`POST /v1/auth/login`)

1. Find user by email (case-insensitive), verify password with bcrypt
2. Generate access token (15 min) and refresh token (7 days)
3. Set cookies:
   - `__Host-access_token` — HttpOnly, Secure, SameSite=strict, path=/
   - `refresh_token` — HttpOnly, Secure, SameSite=strict, path=/v1/auth/refresh
   - `__Host-csrf_token` — HttpOnly, Secure, SameSite=lax
4. Return CSRF token in response body

### Protected Requests

1. Client sends `__Host-access_token` cookie + `X-CSRF-Token` header
2. `auth_dependency` extracts JWT from cookie, validates signature/expiry, returns the `user_id` as a `UUID` (a non-UUID `sub` — e.g. a stale pre-migration token — is rejected with 401)
3. `CSRFMiddleware` validates `X-CSRF-Token` header matches `__Host-csrf_token` cookie (double-submit pattern)

### Token Refresh (`POST /v1/auth/refresh`)

Validates refresh token, rotates all cookies (access + refresh + CSRF), returns new CSRF token.

### Cookie Security

The `__Host-` prefix enforces: `Secure=true`, no `Domain`, `path=/` — prevents subdomain cookie injection and insecure connections.

## Services

| Service | Purpose |
|---|---|
| `AuthService` | Registration, login, forgot-password, reset-password flows |
| `TokenService` | JWT creation/decoding (HS256, access + refresh tokens) |
| `PasswordService` | Bcrypt hashing via `passlib.CryptContext` |
| `EmailService` | Pure email transport (SMTP or console) — raises `EmailDeliveryError` on failure; no longer knows about registration/reset content |
| `CacheService` | Singleton — required Redis client for caching, rate limiting support, and registration verification |
| `TMDBService` | Singleton — movie search and details via TMDB API (`httpx.AsyncClient`) |
| `MovieService` | Movie lookup, lazy `find_or_create_movie()` from TMDB |
| `LogService` | Viewing log CRUD with movie fetching and poster auto-population |
| `MovieRatingService` | Movie rating create/update/read |
| `UserService` | User info retrieval |
| `StatsService` | Viewing statistics with `asyncio.gather()` for parallel DB queries |
| `NotificationService` | Inbox pagination, batch response assembly, and explicit read state; `create_notification()` delegates to `NotificationUnitOfWork` |
| `OutboundMessageService` | Enqueue-only: renders content (via `app/services/outbound_email_renderer.py`) and writes it to the `outbound_messages` outbox; no SMTP dependency |
| `OutboundMessageDeliveryService` | One claim-and-send delivery cycle: recover stale locks, claim a batch, deliver, retry/fail — used by the worker, not the API |

See [Outbound Email Delivery](docs/technical/outbound-email-delivery.md) for how these compose: renderer registry, transactional outbox, claim protocol, retry/backoff, and the delivery worker.

## Middleware

### Rate Limit Session Middleware (`app/middleware/rate_limit_session_middleware.py`)

- Manages `__Host-session_id` cookies only for the public auth routes that use session-scoped rate limits
- Reuses an existing session only when that session ID is known to Redis
- Cookie is used by `get_rate_limit_key` as a fallback identifier for rate limiting

### CSRF Middleware (`app/middleware/csrf_middleware.py`)

- Protects `POST`, `PUT`, `DELETE`, `PATCH` requests
- Exempt paths: login, register, forgot-password, reset-password, CSRF endpoint, refresh, docs, OpenAPI schema
- Validates `X-CSRF-Token` header matches `__Host-csrf_token` cookie value

### CORS Configuration (`app/config/cors.py`)

- Origins from `CORS_ORIGINS` env var (comma-separated) or dev defaults (`localhost:3000`, `localhost:5173`)
- Credentials enabled, allowed headers include `X-CSRF-Token`

## Schemas

All schemas inherit from `BaseSchema` which enables camelCase alias generation (`alias_generator=to_camel`, `populate_by_name=True`).

| File | Key Schemas |
|---|---|
| `auth_schemas.py` | `RegisterRequest`, `LoginRequest/Response`, `ForgotPasswordRequest`, `ResetPasswordRequest`, `CsrfTokenResponse` |
| `user_schemas.py` | `UserCreateRequest/Response`, `UserResponse` |
| `log_schemas.py` | `LogCreateRequest/Response`, `LogUpdateRequest`, `LogListItem/Response` |
| `movie_schemas.py` | `MovieCreateRequest`, `MovieResponse`, `MovieStats` |
| `movie_rating_schemas.py` | `MovieRatingCreateUpdateRequest`, `MovieRatingResponse`, `MovieRatingStats` |
| `stats_schemas.py` | `StatsSummary`, `StatsDistribution`, `StatsPace`, `StatsResponse` |
| `tmdb_schemas.py` | `TMDBMovieSearchResult`, `TMDBMovieDetails` |
| `error_schemas.py` | `ErrorSchema` (error_code_name, error_code, error_message, error_description) |
| `notification_schemas.py` | Common notification response, list query/response, creation data, bulk-read response |

## Utils

| Utility | Purpose |
|---|---|
| `auth_utils.py` | Cookie management: `set_auth_cookies()`, `set_csrf_cookie()`, `clear_auth_cookies()`, `set_rate_limit_session_id()` |
| `rate_limit_utils.py` | Rate limit key function (`get_rate_limit_key`) and custom 429 exception handler |
| `exceptions_utils.py` | `AppException` — custom exception wrapping `ErrorSchema` |
| `error_codes_utils.py` | `ErrorCodes` class with predefined error schemas |
| `sanitize_utils.py` | HTML tag stripping, name/handle pattern validation |
| `datetime_utils.py` | UTC date/datetime conversion helpers |
| `id_utils.py` | `is_valid_uuid()` string validation |
| `cursor_pagination_utils.py` | Versioned opaque cursor encoding and strict decoding |

## User Repository Deletion Methods

The user repository provides two deletion strategies:

- `delete_user()`: Soft delete (sets `deleted=True`)
- `delete_user_oblivion()`: GDPR-compliant deletion that obscures all user information

## TMDB Integration

`TMDBService` handles external API calls to The Movie Database:

- Search movies by title → `TMDBMovieSearchResult`
- Get movie details by ID → `TMDBMovieDetails`
- Base URL: `https://api.themoviedb.org/3/`
- Auth: Bearer token via `Authorization` header
- Client: `httpx.AsyncClient` (singleton, closed during app shutdown)

## Caching

`CacheService` provides the shared Redis client:

- **Required dependency:** Redis must be reachable during FastAPI startup. `app/__init__.py` initializes `CacheService`, pings Redis via `health_check()`, and raises `RuntimeError` if Redis is unavailable.
- **Configuration:** `REDIS_URL` selects the Redis instance and defaults to `redis://localhost:6379/0`; there is no `REDIS_ENABLED` toggle.
- **Error behavior:** `CacheService` is a low-level wrapper and lets Redis errors propagate. Higher-level callers decide whether to fail open or fail closed. `LogCacheRepository` catches cache errors and falls back to PostgreSQL; registration verification, rate limiting, stats caching, and TMDB caching require Redis to remain healthy.
- **Serialization:** Callers pass JSON-ready dicts to `set()` and revalidate after `get()` — keeps CacheService model-agnostic. `LogCacheRepository` serializes ORM rows through an internal Pydantic mirror model.
- **Key naming:** `cinelog:{entity}:{identifier}` — key construction is the caller's responsibility
- **Default TTL:** 300 seconds (5 minutes), configurable via `REDIS_DEFAULT_TTL`
- **Pattern invalidation:** Uses `SCAN` (not `KEYS`) for production-safe pattern-based cache invalidation
- **Lifecycle:** Initialized during app startup in `app/__init__.py`, closed during shutdown

## PostgreSQL Connection

Connection management lives in `app/db/postgres.py`:

- `DATABASE_URL` env var (a `postgresql+asyncpg://` connection string) is required; startup fails without it
- `init_postgres_engine()` creates a process-wide async engine (`pool_pre_ping=True`) and session factory
- `get_async_session()` yields `AsyncSession` instances for repositories
- `close_postgres_engine()` disposes the engine during app shutdown

## Testing Approach

Tests use:

- `pytest` for test framework
- `pytest-postgresql` for repository tests against a real ephemeral PostgreSQL instance (per-test databases via `DatabaseJanitor`)
- `freezegun` for time-based testing
- Mock pattern for isolating services from repositories

## Migrations

Database schema migrations are managed with **Alembic** (`alembic/` directory):

```bash
make db-schema-migrate          # Apply pending migrations (alembic upgrade head)
make db-schema-migrate-dry-run  # Preview SQL without applying (alembic upgrade head --sql)
make db-schema-rollback         # Roll back one revision (alembic downgrade -1)
```

In production, the `db-migrate` service in `docker-compose.prod.yml` runs `alembic upgrade head` before the API and the email worker start.

Migration revision ids equal their filename stem and are constrained to Alembic's default `alembic_version.version_num` column width (`VARCHAR(32)`) — `007_create_outbound_messages` is intentionally shorter than a `..._table` suffix would suggest for exactly this reason.

See `docs/technical/postgres-migration.md` for the history of the MongoDB → PostgreSQL migration, and [Outbound Email Delivery](docs/technical/outbound-email-delivery.md) for migration `007_create_outbound_messages`.
