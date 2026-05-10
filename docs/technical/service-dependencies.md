# Service Dependencies

Controllers receive services through FastAPI `Depends(...)`. Each service owns and instantiates its repositories directly — there is no separate repository dependency layer or protocol indirection.

## Conventions

- Service providers live in `app/dependencies/service_dependency.py`.
- Each provider is `@lru_cache`-d, so it returns the same process-wide service instance.
- Each service constructs its own repositories. Tests can pass a mock via the service's optional repository constructor parameters; production code does not.
- Cache decorators (currently only `LogCacheRepository`) are wired at the dependency layer — the service stays cache-agnostic.
- Controllers do not hold module-level service singletons. Endpoints use `Depends(get_*_service)` exclusively.

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

Because every `get_*_service` provider is `@lru_cache`-d, the same instance is returned to the controller (via `Depends`) and to the test code (via direct call). This gives two equally valid override patterns. Pick the one that matches how much of the service you want to replace.

### Pattern 1 — Patch a single method

Use this when the test only cares about one method on the service. The cached instance keeps its identity; only the named method is swapped for the duration of the test, then restored automatically.

```python
from unittest.mock import AsyncMock, patch

from app.dependencies.service_dependency import get_log_service


class TestCreateLog:
    @patch.object(get_log_service(), "create_log", new_callable=AsyncMock)
    def test_create_log_success(self, mock_create_log, client, sample_log_response):
        mock_create_log.return_value = sample_log_response

        response = client.post("/v1/logs/", json={...}, cookies={...})

        assert response.status_code == 201
        mock_create_log.assert_awaited_once()
```

This is the dominant pattern in `tests/units/controllers/` because most controller tests exercise one endpoint at a time.

> ⚠️ Do not call `get_log_service.cache_clear()` (or any `get_*_service.cache_clear()`) during a test that uses `patch.object(get_*_service(), ...)`. The decorator evaluates `get_*_service()` once at import and patches that instance; clearing the cache makes the controller resolve a fresh, unpatched instance on the next request, and the test would silently pass for the wrong reason — or fail in a confusing way.

### Pattern 2 — Replace the whole service via `dependency_overrides`

Use this when the test needs to swap out many methods on the service, or when the test fixture needs full control over how the service behaves (e.g. a fully-faked service with shared state across calls).

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

`dependency_overrides` is keyed by the provider function itself, **not** the service instance — that's what makes the override active for the duration of the request.

### Combining with auth overrides

Most controller tests also need to bypass `auth_dependency`. The two override styles compose cleanly:

```python
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_log_service


@pytest.fixture
def override_auth():
    return lambda: PydanticObjectId()


@patch.object(get_log_service(), "create_log", new_callable=AsyncMock)
def test_create_log_authenticated(mock_create_log, client, override_auth):
    app.dependency_overrides[auth_dependency] = override_auth
    mock_create_log.return_value = ...
    try:
        response = client.post("/v1/logs/", ...)
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(auth_dependency, None)
```

Always remove your override at the end of the test — `dependency_overrides` is module-level state and leaks across tests if not cleaned up. Prefer `pop(specific_key, None)` over `app.dependency_overrides = {}`: the latter silently wipes overrides set by other fixtures (e.g. an autouse session fixture) and is a footgun. Reserve `app.dependency_overrides = {}` for top-level pytest teardown fixtures that intentionally own all override state.

### When to prefer which pattern

| Use Pattern 1 (`patch.object`) when | Use Pattern 2 (`dependency_overrides`) when |
|---|---|
| Mocking one or two methods on the service | Replacing the entire service with a fake |
| Test only exercises a single endpoint | Test exercises multiple endpoints with cross-call state |
| You want minimal setup and automatic cleanup | You need to control method behavior in a fixture |

## Why no protocol layer?

A repository `Protocol` would only be useful if a second backend implementation existed. Today the repositories return Beanie `Document` subclasses (`Log`, `Movie`, `User`, `MovieRating`), which carry MongoDB-specific machinery (`PydanticObjectId`, `find_one`, `save`, `Settings`/indexes). A non-Mongo repository couldn't satisfy that contract without dragging Mongo concepts into a different store, so the abstraction wouldn't deliver real flexibility.

If a second backend is added later, the prerequisite is splitting persistence-neutral domain types from the Beanie `Document` models — at that point repository protocols become genuinely load-bearing and can be reintroduced.

## Related Docs

- [Redis Caching](redis-caching.md)
- [TMDB Service](tmdb-service.md)
