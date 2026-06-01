# Service Dependencies

Controllers receive services through FastAPI `Depends(...)`.

## Conventions

- Service providers live in `app/dependencies/service_dependency.py`.
- Repository providers live in `app/dependencies/repository_dependency.py`.
- Each provider is `@lru_cache`-d, so it returns the same process-wide instance.
- Controllers use `Depends(get_*_service)` exclusively.

## Repository Provider Guardrails

`get_movie_repository()`, `get_user_repository()`, and `get_movie_rating_repository()` are the runtime activation gates for mixed-mode persistence:

- `DB_BACKEND` unset or `mongo` -> returns Mongo-backed `MovieRepository`.
- `DB_BACKEND` unset or `mongo` -> returns Mongo-backed `UserRepository`.
- `DB_BACKEND` unset or `mongo` -> returns Mongo-backed `MovieRatingRepository`.
- `DB_BACKEND=postgres` while mixed-mode is unsafe -> raises `RepositoryActivationError` (fail-fast).

This prevents accidental cutover while:

- Mongo `LogRepository` and `MovieRatingRepository` still depend on ObjectId `movie_id` references.
- JWT `sub` values, `auth_dependency`, profile ownership checks, and user-scoped cache keys still depend on ObjectId `user_id` references.
- `MovieRatingService`, `LogService`, and `StatsService` still rely on mixed Mongo user/movie identifiers for rating lookups.

## Service Providers

| Provider | Service |
|---|---|
| `get_auth_service()` | `AuthService` |
| `get_auth_rate_limit_service()` | `AuthRateLimitService` |
| `get_user_service()` | `UserService` |
| `get_movie_service()` | `MovieService` |
| `get_movie_rating_service()` | `MovieRatingService` |
| `get_log_service()` | `LogService` (wraps `LogRepository` with `LogCacheRepository`) |
| `get_stats_service()` | `StatsService` (wraps `LogRepository` with `LogCacheRepository`) |

## Endpoint Usage

```python
from app.dependencies.service_dependency import get_log_service
from app.services.log_service import LogService


@router.post("/")
async def create_log(
    body: LogCreateRequest,
    user_id: PydanticObjectId = Depends(auth_dependency),
    log_service: LogService = Depends(get_log_service),
) -> LogCreateResponse:
    return await log_service.create_log(user_id=user_id, request=body)
```

## Test Overrides

Because every `get_*_service` provider is `@lru_cache`-d, the same instance is returned to the controller (via `Depends`) and to test code (via direct call).

### Pattern 1: Patch a single service method

```python
from unittest.mock import AsyncMock, patch

from app.dependencies.service_dependency import get_log_service


@patch.object(get_log_service(), "create_log", new_callable=AsyncMock)
def test_create_log_success(mock_create_log, client):
    mock_create_log.return_value = ...
    response = client.post("/v1/logs/", json={...}, cookies={...})
    assert response.status_code == 201
```

### Pattern 2: Replace full service via `dependency_overrides`

```python
from unittest.mock import AsyncMock, MagicMock

from app import app
from app.dependencies.service_dependency import get_log_service


def test_create_then_list(client):
    fake_log_service = MagicMock()
    fake_log_service.create_log = AsyncMock(return_value=...)
    fake_log_service.get_user_logs_by_handle = AsyncMock(return_value=...)

    app.dependency_overrides[get_log_service] = lambda: fake_log_service
    try:
        client.post("/v1/logs/", json={...})
        client.get("/v1/logs/myhandle")
    finally:
        app.dependency_overrides.pop(get_log_service, None)
```

## Related Docs

- [Redis Caching](redis-caching.md)
- [TMDB Service](tmdb-service.md)
- [Postgres Migration](postgres-migration.md)
