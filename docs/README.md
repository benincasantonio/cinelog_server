# Cinelog Server Documentation

Welcome to the Cinelog Server documentation.

## Functional Docs

User-facing documentation covering features, flows, and API usage from the consumer perspective.

| Document | Description |
|----------|-------------|
| [Authentication](functional/authentication.md) | Auth flows, API usage, CSRF guide |
| [TMDB Movie Service](functional/tmdb-service.md) | Movie search and details endpoints, data flow, response fields |

## Technical Docs

Developer-facing documentation covering infrastructure, implementation details, and internal systems.

| Document | Description |
|----------|-------------|
| [Authentication](technical/authentication.md) | Auth implementation internals, middleware, cookie config |
| [CORS Configuration](technical/cors-configuration.md) | CORS environment variables and behavior |
| [E2E Testing](technical/e2e-testing.md) | Setup and run end-to-end tests |
| [Migrations](technical/migrations.md) | Database migration system |
| [Redis Caching](technical/redis-caching.md) | Cache layer configuration, design, and usage |
| [Stats Caching](technical/stats-caching.md) | Stats caching strategy, TTL, and invalidation triggers |
| [TMDB Service](technical/tmdb-service.md) | Singleton lifecycle, HTTP client, cache keys, MovieService integration |
| [Pydantic Types and Validators](technical/pydantic_types_and_validators.md) | Reusable Annotated validation types by domain |

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
| `make test-e2e` | Start e2e MongoDB, run e2e tests, then stop e2e MongoDB |
| `make migrate` | Run pending database migrations with confirmation |
| `make migrate-dry-run` | Preview pending migrations without applying changes |
| `make lint` | Run Ruff linter |
| `make format` | Format code with Ruff and apply auto-fixes |
| `make typecheck` | Run mypy type checking for `app/` |
| `make security` | Run Bandit security scan and pip-audit dependency scan |
| `make run` | Run API locally via `python main.py` |
| `make docker-up` | Start local Docker stack (`docker-compose.local.yml`) |
| `make docker-down` | Stop local Docker stack (`docker-compose.local.yml`) |
