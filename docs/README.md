# Cinelog Server Documentation

Welcome to the Cinelog Server documentation.

## Functional Docs

User-facing documentation covering features, flows, and API usage from the consumer perspective.

| Document | Description |
|----------|-------------|
| [Authentication](functional/authentication.md) | Auth flows, API usage, CSRF guide |
| [Logs API](functional/logs-api.md) | Create, update, delete, and list viewing logs |
| [Profile Visibility](functional/profile-visibility.md) | User profile visibility settings and public profile lookup |
| [Rate Limiting](functional/rate-limiting.md) | Rate limits per endpoint, response headers, and 429 behavior |
| [TMDB Movie Service](functional/tmdb-service.md) | Movie search and details endpoints, data flow, response fields |

## Technical Docs

Developer-facing documentation covering infrastructure, implementation details, and internal systems.

| Document | Description |
|----------|-------------|
| [Authentication](technical/authentication.md) | Auth implementation internals, middleware, cookie config |
| [Code Quality CI](technical/code-quality-ci.md) | GitHub Actions quality gates for lint, format, type checking, and security |
| [CORS Configuration](technical/cors-configuration.md) | CORS environment variables and behavior |
| [Deployment Options](technical/deployment-options.md) | VPS and optional Vercel deployment guidance |
| [E2E Testing](technical/e2e-testing.md) | Setup and run end-to-end tests |
| [Migrations](technical/migrations.md) | Database migration system |
| [Postgres Migration](technical/postgres-migration.md) | PostgreSQL setup, deterministic IDs, and cutover guardrails |
| [Profile Visibility](technical/profile-visibility.md) | Visibility field, service logic, migration, and friends-only stub |
| [Pydantic Types and Validators](technical/pydantic_types_and_validators.md) | Reusable Annotated validation types by domain |
| [Rate Limiting](technical/rate-limiting.md) | slowapi setup, Redis backend, endpoint decoration, test strategy |
| [Redis Caching](technical/redis-caching.md) | Cache layer configuration, design, and usage |
| [Service Dependencies](technical/service-dependencies.md) | Service providers, FastAPI `Depends` wiring, test overrides |
| [Stats Caching](technical/stats-caching.md) | Stats caching strategy, TTL, and invalidation triggers |
| [TMDB Service](technical/tmdb-service.md) | Singleton lifecycle, HTTP client, cache keys, MovieService integration |

## Quick Links

- **API Base URL**: `http://localhost:5009`
- **Development Guide**: [AGENTS.md](../AGENTS.md)
- **Architecture Reference**: [ARCHITECTURE.md](../ARCHITECTURE.md)

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install runtime dependencies (`uv sync`) |
| `make dev` | Install runtime + development dependencies and configure git hooks |
| `make hooks` | Configure git pre-commit hooks (lint, format, typecheck) |
| `make test-unit` | Run unit tests with coverage report |
| `make test-e2e` | Run e2e tests against Mongo by default, or Postgres with `E2E_BACKEND=postgres` |
| `make migrate` | Run pending database migrations with confirmation |
| `make migrate-dry-run` | Preview pending migrations without applying changes |
| `make db-data-migrate` | Run pending PostgreSQL data migrations from `db_migrations/` |
| `make db-data-migrate-dry-run` | Preview pending PostgreSQL data migrations without applying changes |
| `make migrate-all` | Run all pending Mongo migrations, PostgreSQL schema migrations, and PostgreSQL data migrations |
| `make migrate-all-dry-run` | Preview all pending migration systems without applying changes |
| `make db-schema-migrate` | Run Alembic schema migrations against `DATABASE_URL` |
| `make db-schema-migrate-dry-run` | Print Alembic schema migration SQL without applying it |
| `make db-schema-rollback` | Roll back the latest Alembic schema migration |
| `make lint` | Run Ruff linter |
| `make format` | Format code with Ruff and apply auto-fixes |
| `make format-check` | Check Ruff formatting without modifying files |
| `make typecheck` | Run mypy type checking for `app/` |
| `make security` | Run Bandit security scan and pip-audit dependency scan |
| `make run` | Run API locally via `python main.py` |
| `make docker-up` | Start local Docker stack (`docker-compose.local.yml`) |
| `make docker-down` | Stop local Docker stack (`docker-compose.local.yml`) |
