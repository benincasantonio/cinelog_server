# AGENTS.md

This file provides operational guidance for AI coding agents working with this repository.

## Project Overview

Cinelog is a FastAPI-based movie logging application that allows users to track movies they've watched, rate them, and manage their viewing history. The backend integrates with The Movie Database (TMDB) API for movie information and uses MongoDB with Beanie ODM for data persistence.

## Development Commands

**Important:** Always check the `Makefile` for available scripts before running raw commands. The `Makefile` wraps common operations and ensures consistent usage across local dev and CI.

### Available Make Targets

| Target | Description |
|---|---|
| `make install` | Install runtime dependencies |
| `make dev` | Install dev dependencies + set up git hooks |
| `make hooks` | Set up git hooks only |
| `make test-unit` | Run unit tests with coverage |
| `make test-e2e` | Run end-to-end tests (auto starts/stops Docker) |
| `make lint` | Run Ruff linter |
| `make format` | Run Ruff formatter + auto-fix |
| `make typecheck` | Run mypy static type checking |
| `make security` | Run Bandit security scan |
| `make dependency-audit` | Run pip-audit dependency vulnerability scan |
| `make run` | Start the application locally |
| `make docker-up` | Start local Docker environment |
| `make docker-down` | Stop local Docker environment |
| `make migrate` | Run database migrations |
| `make migrate-dry-run` | Dry-run database migrations |

### Running the Application

**Local development (with auto-reload):**

```bash
make dev
make run
```

The API will be available at `http://127.0.0.1:5009`

**Docker Compose (recommended for development):**

```bash
make docker-up
```

This starts both MongoDB (as a single-node replica set for transaction support) and the API service with hot-reload enabled.

### Testing

**Run unit tests:**

```bash
make test-unit
```

**Run e2e tests:**

```bash
make test-e2e
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
- `REDIS_ENABLED`: Enable Redis caching (default: `false`)
- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `REDIS_DEFAULT_TTL`: Default cache TTL in seconds (default: `300`)

### Git Hooks

Pre-commit hooks enforce linting (Ruff), formatting (Ruff), and type checking (mypy) before each commit.

**Auto-installed with dev setup:**

```bash
make dev
```

**Manual setup (if already installed deps):**

```bash
make hooks
```

Both commands set `core.hooksPath` to `.githooks/`. The pre-commit hook runs `ruff check --fix`, `ruff format --check`, and `mypy` against the `app/` directory.

### Security Scanning

```bash
make security
```

Runs both **Bandit** (static analysis for common security issues) and **pip-audit** (dependency vulnerability scanning) against the codebase. These checks also run automatically in CI via the security workflow.

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

6. **Commit messages** must follow conventional commits format: `type(scope): description`
   - Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`
   - Scope: the module or area of change (e.g., `mypy`, `auth`, `rating`, `ci`)
   - Example: `chore(mypy): add configuration and enforce type checking in CI`

7. **Create a pull request** when the developer asks for it:
   ```bash
   gh pr create
   ```
   See https://cli.github.com/manual/gh_pr_create for options.

## Naming Conventions

- **Utility modules** in `app/utils/` must follow the `_utils.py` suffix naming convention (e.g., `validator_utils.py`, `sanitize_utils.py`). This ensures consistency and discoverability across the codebase.

## Types and Validators

Reusable validation logic lives in `app/types/`, organized by business domain. Each file contains both the validation functions and the resulting Annotated type aliases.

**File structure:**

| File | Purpose |
|---|---|
| `app/types/common_validation.py` | Cross-domain validators shared by multiple domains |
| `app/types/<domain>_validation.py` | Domain-specific validators (e.g., `user_validation.py`, `log_validation.py`) |
| `app/types/__init__.py` | Re-exports all public types for convenient imports |

**Rules:**

- Never define inline `@field_validator` methods in schemas when a reusable Annotated type already exists in `app/types/`.
- When adding a new validator, place it in the appropriate domain file. If it spans multiple domains, put it in `common_validation.py`.
- Schemas must import types from `app.types` (the package), not from individual sub-modules directly.
- Each domain file must include module-level documentation listing the exported types and their purpose.
- Never create `Optional{TypeName}` aliases in `app/types/`. For optional validated fields, write `TypeName | None` inline in the schema instead (e.g. `ProfileVisibilityStr | None`, `WatchedWhereStr | None`).

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
9. **Types** (`app/types/`) → Reusable Annotated validation types, organized by domain
10. **Utils** (`app/utils/`) → Shared utilities

## Documentation

When working on a feature, bug fix, or any topic that introduces or changes behavior, always write documentation for it:

- Place documentation in the `docs/` directory, organized into two subfolders:
  - `docs/functional/` — user-facing docs (features, API usage, flows)
  - `docs/technical/` — developer-facing docs (implementation details, infrastructure, configuration)
- Topics that have both functional and technical aspects should have a doc in each folder, cross-linked via "See Also" sections
- Add a link to the new document in [`docs/README.md`](docs/README.md)
- If documentation already exists for the topic, update it to reflect the changes

See [`docs/README.md`](docs/README.md) for existing topic-specific guides.
