# E2E Testing Setup Guide

This guide walks through setting up and running end-to-end tests locally.

## Prerequisites

- **Docker** - For running MongoDB
- **Python 3.12+** - With `uv` installed
- **.env file** - With `TMDB_API_KEY` configured

## Quick Start

```bash
# 0. Sync dependencies
uv sync --group dev

# 1. Run e2e tests with Docker MongoDB lifecycle managed automatically
make test-e2e
```

## Infrastructure Components

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| MongoDB | `cinelog_mongo_e2e` | 27018 | Test database |

## Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.e2e.yml` | Docker infrastructure |
| `pyproject.toml` | pytest-asyncio settings (`[tool.pytest.ini_options]`) |
| `tests/e2e/conftest.py` | Test fixtures |

## Environment Variables

The e2e tests automatically configure these (via `conftest.py`):

```bash
MONGODB_HOST=localhost
MONGODB_PORT=27018
MONGODB_DB=cinelog_e2e_db
```

**Note:** `TMDB_API_KEY` is loaded from `.env` for log tests that fetch movie data.

## Test Structure

```
tests/e2e/
├── conftest.py          # Fixtures (MongoDB, Firebase, cleanup)
├── test_auth_e2e.py     # Registration tests
├── test_user_e2e.py     # User info & logs tests
└── test_log_e2e.py      # Log CRUD tests
```

## Debugging

### Connect to MongoDB
```bash
mongosh --port 27018
```

### Run specific test
```bash
uv run pytest tests/e2e/test_auth_e2e.py::TestAuthE2E::test_register_success -v
```

## CI/CD

The GitHub workflow (`.github/workflows/e2e_tests.yml`) runs e2e tests automatically.

**Required secrets:**
- `TMDB_API_KEY` - For movie data fetching
