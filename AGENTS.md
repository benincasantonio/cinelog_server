# AGENTS.md

This file provides operational guidance for AI coding agents working with this repository.

## Project Overview

Cinelog is a FastAPI-based movie logging application that allows users to track movies they've watched, rate them, and manage their viewing history. The backend integrates with The Movie Database (TMDB) API for movie information and uses MongoDB with Beanie ODM for data persistence.

## Development Commands

### Running the Application

**Local development (with auto-reload):**

```bash
uv sync --group dev
uv run python main.py
```

The API will be available at `http://127.0.0.1:5009`

**Docker Compose (recommended for development):**

```bash
docker-compose -f docker-compose.local.yml up --build
```

This starts both MongoDB (as a single-node replica set for transaction support) and the API service with hot-reload enabled.

### Testing

**Run all tests:**

```bash
uv run pytest
```

**Run tests with coverage:**

```bash
uv run pytest --cov=app --cov-report=html
```

**Run specific test file:**

```bash
uv run pytest tests/services/test_auth_service.py
```

**Run specific test:**

```bash
uv run pytest tests/services/test_auth_service.py::test_function_name
```

### Environment Setup

Required environment variables (see `.env`):

- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `TMDB_API_KEY`: The Movie Database API key
- `MONGODB_URI`: Full MongoDB connection string (e.g., `mongodb://localhost:27017` or `mongodb+srv://host/cinelog_db`)
- `MONGODB_HOST`: MongoDB host (default: localhost) — only used if `MONGODB_URI` not set
- `MONGODB_PORT`: MongoDB port (default: 27017) — only used if `MONGODB_URI` not set
- `MONGODB_DB`: MongoDB database name (default: cinelog_db) — only used if `MONGODB_URI` not set

## Development Flow

All work must be tied to a GitHub issue. Follow this workflow:

1. **A GitHub issue number must always be provided** before starting work. If none is given, ask for one.

2. **Create a branch from the issue** using the GitHub CLI:
   ```bash
   gh issue develop <issue-number> --checkout
   ```
   If `gh` CLI is not installed, suggest installing it: https://cli.github.com/

3. **Write unit tests for all new code.** Every new function, method, or behavior must have corresponding unit tests.

4. **Do not commit changes autonomously.** Let the developer review changes step by step. Only commit when explicitly asked.

5. **Create a pull request** when the developer asks for it:
   ```bash
   gh pr create
   ```
   See https://cli.github.com/manual/gh_pr_create for options.

## Architecture

> For a deeper architectural overview, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

### Layered Architecture

The codebase follows a clean layered architecture:

1. **Controllers** (`app/controllers/`): FastAPI route handlers that define API endpoints
2. **Services** (`app/services/`): Business logic layer that orchestrates repository operations and external integrations (e.g., `AuthService`, `TMDBService`)
3. **Repositories** (`app/repositories/`): Data access layer using Beanie ODM
4. **Models** (`app/models/`): Beanie document models representing database entities
5. **Schemas** (`app/schemas/`): Pydantic models for request/response validation
6. **Utils** (`app/utils/`): Shared utilities for hashing, JWT tokens, etc.

### Key Patterns

**Dependency Flow:**

- Controllers instantiate services with required repositories
- Services contain business logic and call repositories
- Repositories handle direct database operations using Beanie models

**Error Handling:**

- Custom `AppException` class with structured `ErrorSchema` objects
- Centralized error codes in `app/utils/error_codes.py`
- Global exception handler in `app/__init__.py` converts `AppException` to JSON responses

**Authentication:**

- JWT-based authentication using access tokens
- `auth_dependency` in `app/dependencies/auth_dependency.py` validates tokens
- Tokens generated via `generate_access_token` in `app/utils/access_token_utils.py`

### Base Entity Pattern

All database models inherit from `BaseEntity` (`app/models/base_entity.py`) which provides:

- Soft delete support (`deleted`, `deletedAt`)
- Automatic timestamps (`createdAt`, `updatedAt`)
- Common indexes

### Data Models

**Core Entities:**

- `User`: User accounts with authentication (email/handle login supported)
- `Movie`: Movie metadata (linked to TMDB via `tmdbId`)
- `Log`: Movie viewing records with ratings, dates, and viewing location
- `MovieRating`: Movie rating collection data

### Testing Approach

Tests use:

- `pytest` for test framework
- `mongomock` for mocking MongoDB in unit tests
- `freezegun` for time-based testing
- Mock pattern for isolating services from repositories

## Important Implementation Details

### User Repository Deletion Methods

The `UserRepository` provides two deletion strategies:

- `delete_user()`: Soft delete (sets `deleted=True`)
- `delete_user_oblivion()`: GDPR-compliant deletion that obscures all user information

### Authentication Flow

1. Login/Register endpoints return JWT token and user info
2. Protected endpoints use `Depends(auth_dependency)` to require authentication
3. Token validation checks expiration and signature using `JWT_SECRET_KEY`

### TMDB Integration

`TMDBService` handles external API calls to The Movie Database:

- Search movies by title
- Returns structured `TMDBMovieSearchResult` Pydantic models

### MongoDB Connection

Connection is established in `app/__init__.py`:

- Uses environment variables for configuration (`MONGODB_URI` or `MONGODB_HOST`/`MONGODB_PORT`/`MONGODB_DB`)
- Creates an async PyMongo `AsyncMongoClient` for Beanie ODM operations
- Beanie 2.0.1 provides async ODM functionality using Pydantic v2 models
- `directConnection=True` is used for single-node replica sets in local development

### Migrations

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

## Documentation

When working on a feature, bug fix, or any topic that introduces or changes behavior, always write documentation for it:

- Place documentation in the `docs/` directory as a **single file per topic** (e.g., `docs/authentication.md`, `docs/cors-configuration.md`)
- Each file must cover both **functional aspects** (what the feature does, how it behaves, user-facing details) and **technical aspects** (implementation details, architecture decisions, code patterns)
- Add a link to the new document in [`docs/README.md`](docs/README.md)
- If documentation already exists for the topic, update it to reflect the changes

See [`docs/README.md`](docs/README.md) for existing topic-specific guides.
