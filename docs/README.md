# Cinelog Server Documentation

Welcome to the Cinelog Server documentation.

## Guides

| Document | Description |
|----------|-------------|
| [E2E Testing](e2e-testing.md) | Setup and run end-to-end tests |
| [CORS Configuration](cors-configuration.md) | CORS environment and behavior specification |
| [Authentication](authentication.md) | **NEW** Auth system (JWT, Cookies, CSRF) |

## Quick Links

- **API Base URL**: `http://localhost:5009`
- **Main README**: [CLAUDE.md](../CLAUDE.md)

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install runtime dependencies (`uv sync`) |
| `make dev` | Install runtime + development dependencies |
| `make test-unit` | Run unit tests with coverage report |
| `make test-e2e` | Start e2e MongoDB, run e2e tests, then stop e2e MongoDB |
| `make lint` | Run Ruff linter |
| `make format` | Format code with Ruff and apply auto-fixes |
| `make typecheck` | Run mypy type checking for `app/` |
| `make security` | Run Bandit security scan for `app/` |
| `make run` | Run the API locally via `python main.py` |
| `make docker-up` | Start local Docker stack (`docker-compose.local.yml`) |
| `make docker-down` | Stop local Docker stack (`docker-compose.local.yml`) |
