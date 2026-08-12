# Service Dependencies

Controllers receive services through FastAPI `Depends(...)`.

## Conventions

- Service providers live in `app/dependencies/service_dependency.py`.
- Repository providers live in `app/dependencies/repository_dependency.py`.
- Each provider is `@lru_cache`-d, so it returns the same process-wide instance.
- Controllers use `Depends(get_*_service)` exclusively.

## Repository Providers

`get_movie_repository()`, `get_user_repository()`, `get_movie_rating_repository()`, `get_log_repository()`, and `get_stats_repository()` return PostgreSQL repository implementations. `StatsRepository` is a cross-table read repository and does not correspond to a database table. Services type-hint against the `*RepositoryProtocol` interfaces in `app/repository/`.

## Service Providers

| Provider | Service |
|---|---|
| `get_auth_service()` | `AuthService` |
| `get_auth_rate_limit_service()` | `AuthRateLimitService` |
| `get_user_service()` | `UserService` |
| `get_follow_service()` | `FollowService` (composes `NotificationService` for `follow.started`) |
| `get_movie_service()` | `MovieService` |
| `get_movie_rating_service()` | `MovieRatingService` |
| `get_log_service()` | `LogService` (wraps the log repository with `LogCacheRepository`) |
| `get_notification_service()` | `NotificationService` |
| `get_stats_service()` | `StatsService` with `StatsRepository`; response caching is composed through `StatsCacheService` |

## Endpoint Usage

```python
from uuid import UUID

from app.dependencies.service_dependency import get_log_service
from app.services.log_service import LogService


@router.post("/")
async def create_log(
    body: LogCreateRequest,
    user_id: UUID = Depends(auth_dependency),
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
- [Statistics Query](stats-query.md)
- [Postgres Migration](postgres-migration.md)
