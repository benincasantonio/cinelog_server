# E2E Testing Setup Guide

This guide walks through setting up and running end-to-end tests locally.

## Prerequisites

- **Docker** - For running PostgreSQL and Redis
- **Python 3.12+** - With `uv` installed
- **.env file** - With `TMDB_API_KEY` configured

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

**Note:** `TMDB_API_KEY` is loaded from `.env` for log tests that fetch movie data.

## Test Structure

```
tests/e2e/
├── conftest.py          # Fixtures and database cleanup
├── test_auth_e2e.py     # Registration tests
├── test_movie_rating_e2e.py # Movie rating tests
├── test_user_e2e.py     # User info & logs tests
└── test_log_e2e.py      # Log CRUD tests
```

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

The workflow runs `uv run alembic upgrade head` before pytest so the schema is created from the same Alembic revisions used in development.

**Required secrets:**
- `TMDB_API_KEY` - For movie data fetching
