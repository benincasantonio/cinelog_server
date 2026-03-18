# Architecture

This document is the definitive architecture reference for the Cinelog Server codebase.

## Layered Architecture

The codebase follows a clean layered architecture:

1. **Controllers** (`app/controllers/`) — FastAPI route handlers that define API endpoints
2. **Services** (`app/services/`) — Business logic layer that orchestrates repository operations and external integrations
3. **Repositories** (`app/repositories/`) — Data access layer using Beanie ODM
4. **Models** (`app/models/`) — Beanie document models representing database entities
5. **Schemas** (`app/schemas/`) — Pydantic models for request/response validation
6. **Dependencies** (`app/dependencies/`) — FastAPI dependency injection (e.g., JWT auth)
7. **Middleware** (`app/middleware/`) — Request processing middleware (e.g., CSRF protection)
8. **Config** (`app/config/`) — Application configuration (e.g., CORS)
9. **Utils** (`app/utils/`) — Shared utilities (exceptions, error codes, cookie management, sanitization, datetime, ObjectId)

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

## App Initialization

`app/__init__.py` uses a FastAPI lifespan context manager:

**Startup:**
1. Parse MongoDB connection from `MONGODB_URI` or `MONGODB_HOST`/`MONGODB_PORT`/`MONGODB_DB`
2. Initialize `AsyncMongoClient` with `uuidRepresentation="standard"`
3. Initialize Beanie with `[User, Log, Movie, MovieRating]` models

**Shutdown:**
1. Close TMDB service connections (`TMDBService.aclose_all()`)
2. Close MongoDB client

**Middleware stack** (in order): CSRFMiddleware → CORSMiddleware

**Global exception handler** catches `AppException` and returns structured JSON via `ErrorSchema`.

## Key Patterns

**Dependency Flow:**

- Controllers instantiate services with required repositories
- Services contain business logic and call repositories
- Repositories handle direct database operations using Beanie models

**Error Handling:**

- Custom `AppException` class with structured `ErrorSchema` objects
- Centralized error codes in `app/utils/error_codes.py`
- Global exception handler in `app/__init__.py` converts `AppException` to JSON responses

**Singleton Pattern:**

- `TMDBService` uses a thread-safe singleton with `Lock()` — lazy initialization on first `get_instance()` call, single global `httpx.AsyncClient`

**Soft Delete:**

- `BaseEntity.active_filter()` returns `{"deleted": {"$ne": True}}` — used by all repository queries to exclude soft-deleted records

## Base Entity Pattern

All database models inherit from `BaseEntity` (`app/models/base_entity.py`) which provides:

- Soft delete support (`deleted`, `deletedAt`)
- Automatic timestamps (`createdAt`, `updatedAt`) via `@before_event` hooks
- `active_filter(extra)` static method for soft-delete-aware queries
- `model_config` with `populate_by_name=True` for snake_case/camelCase interop

## Data Models

### User (`users` collection)

| Field | Type | Notes |
|---|---|---|
| `email` | `str` | Unique |
| `handle` | `str` | Unique |
| `first_name`, `last_name` | `str` | |
| `bio` | `str \| None` | |
| `date_of_birth` | `datetime \| None` | |
| `password_hash` | `str \| None` | Nullable for legacy accounts |
| `reset_password_code` | `str \| None` | Password reset flow |
| `reset_password_expires` | `datetime \| None` | Password reset expiry |

**Indexes:** `createdAt` (DESC), `deleted` (ASC), `email` (unique), `handle` (unique)

### Movie (`movies` collection)

| Field | Type | Notes |
|---|---|---|
| `tmdb_id` | `int` | Unique — links to TMDB |
| `title` | `str` | |
| `release_date` | `datetime \| None` | |
| `overview` | `str \| None` | |
| `poster_path` | `str \| None` | |
| `vote_average` | `float \| None` | |
| `runtime` | `int \| None` | Minutes |
| `original_language` | `str \| None` | |

**Indexes:** `createdAt` (DESC), `deleted` (ASC), `tmdbId` (unique)

### Log (`logs` collection)

| Field | Type | Notes |
|---|---|---|
| `user_id` | `PydanticObjectId` | FK to User |
| `movie_id` | `PydanticObjectId` | FK to Movie |
| `tmdb_id` | `int` | Denormalized TMDB ID |
| `date_watched` | `datetime` | |
| `viewing_notes` | `str \| None` | |
| `poster_path` | `str \| None` | Denormalized |
| `watched_where` | `Literal` | `cinema`, `streaming`, `homeVideo`, `tv`, `other` |

**Indexes:** `createdAt` (DESC), `deleted` (ASC), `userId` (ASC), `dateWatched` (ASC), `watchedWhere` (ASC), composites: `(userId, dateWatched DESC)`, `(userId, dateWatched DESC, createdAt DESC)`, `(userId, movieId)`, `(tmdbId, dateWatched DESC)`, `(userId, watchedWhere, createdAt)`

### MovieRating (`movie_ratings` collection)

| Field | Type | Notes |
|---|---|---|
| `movie_id` | `PydanticObjectId` | FK to Movie |
| `user_id` | `PydanticObjectId` | FK to User |
| `tmdb_id` | `int` | Denormalized |
| `rating` | `int \| None` | 1–10 validated range |
| `review` | `str \| None` | |

**Indexes:** `createdAt` (DESC), `deleted` (ASC), `movieId` (ASC), `rating` (ASC), `tmdbId` (ASC), `(userId, tmdbId)` (unique composite)

## Authentication Flow

Cookie-based JWT authentication with CSRF double-submit protection.

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
2. `auth_dependency` extracts JWT from cookie, validates signature/expiry, returns `user_id`
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
| `EmailService` | SMTP password reset emails (falls back to console logging in dev) |
| `TMDBService` | Singleton — movie search and details via TMDB API (`httpx.AsyncClient`) |
| `MovieService` | Movie lookup, lazy `find_or_create_movie()` from TMDB |
| `LogService` | Viewing log CRUD with movie fetching and poster auto-population |
| `MovieRatingService` | Movie rating create/update/read |
| `UserService` | User info retrieval |
| `StatsService` | Viewing statistics with `asyncio.gather()` for parallel DB queries |

## Middleware

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
| `error_schema.py` | `ErrorSchema` (error_code_name, error_code, error_message, error_description) |

## Utils

| Utility | Purpose |
|---|---|
| `auth_utils.py` | Cookie management: `set_auth_cookies()`, `set_csrf_cookie()`, `clear_auth_cookies()` |
| `exceptions.py` | `AppException` — custom exception wrapping `ErrorSchema` |
| `error_codes.py` | `ErrorCodes` class with predefined error schemas |
| `sanitize_utils.py` | HTML tag stripping, name/handle pattern validation |
| `datetime_utils.py` | UTC date/datetime conversion helpers |
| `object_id_utils.py` | Safe `to_object_id()` conversion with error handling |

## User Repository Deletion Methods

The `UserRepository` provides two deletion strategies:

- `delete_user()`: Soft delete (sets `deleted=True`)
- `delete_user_oblivion()`: GDPR-compliant deletion that obscures all user information

## TMDB Integration

`TMDBService` handles external API calls to The Movie Database:

- Search movies by title → `TMDBMovieSearchResult`
- Get movie details by ID → `TMDBMovieDetails`
- Base URL: `https://api.themoviedb.org/3/`
- Auth: Bearer token via `Authorization` header
- Client: `httpx.AsyncClient` (singleton, closed during app shutdown)

## MongoDB Connection

Connection is established in `app/__init__.py`:

- Uses environment variables for configuration (`MONGODB_URI` or `MONGODB_HOST`/`MONGODB_PORT`/`MONGODB_DB`)
- Creates an async PyMongo `AsyncMongoClient` for Beanie ODM operations
- Beanie 2.0.1 provides async ODM functionality using Pydantic v2 models
- `directConnection=True` is used for single-node replica sets in local development

## Testing Approach

Tests use:

- `pytest` for test framework
- `mongomock` for mocking MongoDB in unit tests
- `freezegun` for time-based testing
- Mock pattern for isolating services from repositories

## Migrations

The project includes a lightweight database migration system:

**Location:** `migrations/` directory

**Components:**

- `migrations/runner.py` — CLI tool for discovering and running migrations
- `migrations/NNN_name.py` — Individual migration scripts (e.g., `001_movie_ids_to_objectid.py`)

**How it works:**

- Migrations are numbered (`001`, `002`, etc.) and run in order
- Applied migrations are tracked in the `migration_versions` collection
- Uses sync PyMongo (not the async Beanie connection) for direct database operations
- Supports dry-run mode (`--dry-run`) to preview impact before applying

**Running migrations:**

```bash
make migrate           # Run pending migrations with confirmation
make migrate-dry-run   # Preview what would change
uv run python -m migrations.runner --yes  # CI/CD mode (no prompts)
```

**Writing a migration:**

Each migration file must define `up(db, dry_run=False)` and `down(db)` functions:

```python
from pymongo.database import Database

def up(db: Database, dry_run: bool = False) -> None:
    """Apply the migration."""
    pass

def down(db: Database) -> None:
    """Rollback the migration (optional, may be no-op)."""
    pass
```

See `docs/migrations.md` for full documentation.
