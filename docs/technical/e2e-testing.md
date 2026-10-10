# E2E Testing Setup Guide

This guide walks through setting up and running end-to-end tests locally.

## Prerequisites

- **Docker** - For running PostgreSQL and Redis
- **Python 3.12+** - With `uv` installed
- **OpenSSL** - Creates a temporary certificate for HTTPS requests

## Quick Start

```bash
# 0. Sync dependencies
uv sync --group dev

# 1. Run e2e tests (starts Docker services, applies Alembic migrations, runs pytest)
make test-e2e
```

## Infrastructure Components

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| PostgreSQL | `cinelog_postgres_e2e` | 5433 | Test database |
| Redis | `cinelog_redis_e2e` | 6380 | Rate-limit and cache backend |

## Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.e2e.yml` | Docker infrastructure |
| `pyproject.toml` | pytest-asyncio settings (`[tool.pytest.ini_options]`) |
| `tests/e2e/conftest.py` | Test fixtures |

## Environment Variables

The e2e tests automatically configure these (via `conftest.py`):

```bash
DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db
REDIS_URL=redis://localhost:6380/0
```

Pytest starts Uvicorn on a free local HTTPS port for each test. The server runs in the pytest process so email test doubles and the injected movie provider fake work. Uvicorn runs the same FastAPI lifespan used by the application, including PostgreSQL initialization and the Redis startup check. The client accepts only the temporary self-signed test certificate; application Secure cookies remain enabled and are sent over HTTPS.

The tests use real PostgreSQL and Redis. Email delivery remains mocked. Movie metadata uses a deterministic fake injected through `provider_dependency.get_movie_provider`, so a TMDB API key is not required. Provider HTTP and mapping are covered separately by unit tests with mocked upstream responses.

## Test Structure

```
tests/e2e/
├── conftest.py          # Fixtures and database cleanup
├── test_auth_e2e.py     # Registration tests
├── test_movie_rating_e2e.py # Movie rating tests
├── test_movie_identity_consistency_e2e.py # Movie identity data consistency (DB assertions)
├── test_user_e2e.py     # User info & logs tests
└── test_log_e2e.py      # Log CRUD tests
```

## Data Consistency Assertions

Assert through the API where it exposes the fact. For what no endpoint shows, such as duplicate movie rows, `tests/e2e/conftest.py` provides `count_movie_rows`, which queries PostgreSQL through the `postgres_engine` fixture. `logged_in_client` gives each user a separate client for concurrent requests, and `fake_movie_provider.detail_barrier = asyncio.Barrier(n)` makes `n` first imports race.

## Debugging

### Connect to PostgreSQL
```bash
docker exec -it cinelog_postgres_e2e psql -U cinelog -d cinelog_e2e_db
```

### Run specific test
```bash
uv run pytest tests/e2e/test_auth_e2e.py::TestAuthE2E::test_register_success -v
```

## CI/CD

The GitHub workflow (`.github/workflows/e2e_tests.yml`) runs e2e tests automatically on pull requests and pushes to `main`.

The workflow runs `uv run alembic upgrade head` before pytest so the schema is created from the same Alembic revisions used in development. The E2E suite then exercises Uvicorn over HTTPS, including authenticated requests that rely on Secure cookies.
