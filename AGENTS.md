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

3. **Check off acceptance criteria** on the GitHub issue as they are met, using the GitHub CLI:
   ```bash
   # View issue body to find acceptance criteria
   gh issue view <issue-number>
   # Edit the issue body to check off completed criteria
   gh issue edit <issue-number> --body "..."
   ```

4. **Write unit tests for all new code.** Every new function, method, or behavior must have corresponding unit tests.

5. **Do not commit changes autonomously.** Let the developer review changes step by step. Only commit when explicitly asked.

6. **Create a pull request** when the developer asks for it:
   ```bash
   gh pr create
   ```
   See https://cli.github.com/manual/gh_pr_create for options.

## Architecture

For the full architecture reference, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

**Quick orientation — layered architecture:**

1. **Controllers** (`app/controllers/`) → API endpoints
2. **Services** (`app/services/`) → Business logic
3. **Repositories** (`app/repositories/`) → Data access (Beanie ODM)
4. **Models** (`app/models/`) → Database entities
5. **Schemas** (`app/schemas/`) → Request/response validation
6. **Dependencies** (`app/dependencies/`) → FastAPI dependency injection (e.g., JWT auth)
7. **Middleware** (`app/middleware/`) → Request processing middleware (e.g., CSRF protection)
8. **Config** (`app/config/`) → Application configuration (e.g., CORS)
9. **Utils** (`app/utils/`) → Shared utilities

## Documentation

When working on a feature, bug fix, or any topic that introduces or changes behavior, always write documentation for it:

- Place documentation in the `docs/` directory as a **single file per topic** (e.g., `docs/authentication.md`, `docs/cors-configuration.md`)
- Each file must cover both **functional aspects** (what the feature does, how it behaves, user-facing details) and **technical aspects** (implementation details, architecture decisions, code patterns)
- Add a link to the new document in [`docs/README.md`](docs/README.md)
- If documentation already exists for the topic, update it to reflect the changes

See [`docs/README.md`](docs/README.md) for existing topic-specific guides.
