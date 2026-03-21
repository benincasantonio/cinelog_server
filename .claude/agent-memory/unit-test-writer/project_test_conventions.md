---
name: project_test_conventions
description: Testing conventions, fixture patterns, and conftest.py structure for the cinelog_server project
type: project
---

## Test layout

- `tests/conftest.py` — sets JWT env vars via `autouse` fixture; also sets them at module level before imports
- `tests/units/conftest.py` — provides `beanie_test_db` fixture (mongomock_motor, scope=function, drops all collections on teardown)
- `tests/units/services/` — no conftest.py; fixtures live inside test classes or at module level with `@pytest_asyncio.fixture`

## Async test pattern

All async tests use `@pytest.mark.asyncio` + `@pytest_asyncio.fixture`. The project imports both `pytest_asyncio` and `pytest`. Class-level async fixtures are decorated with `@pytest_asyncio.fixture` directly on the method.

## Mocking HTTP (httpx)

Patch `app.services.tmdb_service.httpx.AsyncClient.get` with `new_callable=AsyncMock`. Return a `Mock()` with `.json.return_value = {...}` and `.raise_for_status = Mock()`. For error paths set `.raise_for_status.side_effect = httpx.HTTPStatusError(...)`.

## Mocking CacheService inside TMDBCacheService

`TMDBCacheService` resolves its backing `CacheService` lazily via a `_cache` property. To inject a mock without hitting the singleton:
```python
svc = TMDBCacheService()
svc._cache_instance = AsyncMock()   # the mock CacheService
svc._cache_resolved = True          # skip lazy resolution
```

## Mocking TMDBCacheService inside TMDBService

Pass a `Mock(spec=TMDBCacheService)` with async methods as `AsyncMock` via the `cache=` constructor parameter of `TMDBService`. Helper:
```python
def _make_mock_cache():
    cache = Mock(spec=TMDBCacheService)
    cache.get_search = AsyncMock(return_value=None)
    cache.set_search = AsyncMock()
    cache.get_details = AsyncMock(return_value=None)
    cache.set_details = AsyncMock()
    return cache
```

## CacheService singleton teardown

Tests that touch `CacheService._singleton` must reset it:
```python
def setup_method(self): CacheService._singleton = None
def teardown_method(self): CacheService._singleton = None
```

## Service cleanup

`TMDBService` owns its httpx client by default; always yield and `await service.aclose()` in async fixtures.

## Key files

- `app/services/tmdb_service.py` — constructor: `(api_key, client=None, cache=None)`
- `app/services/tmdb_cache_service.py` — `TMDBCacheService`; exports `TMDB_SEARCH_CACHE_TTL` (600s), `TMDB_DETAILS_CACHE_TTL` (86400s)
- `app/services/cache_service.py` — `CacheService` singleton; `get/set/delete` are async
- `app/schemas/tmdb_schemas.py` — `TMDBMovieSearchResult`, `TMDBMovieDetails` (Pydantic v2, `populate_by_name=True`)
- `tests/units/services/test_tmdb_service.py` — existing + new caching tests
- `tests/units/services/test_tmdb_cache_service.py` — new, covers `TMDBCacheService` in isolation

## Why: raise_for_status

Both `search_movie()` and `get_movie_details()` now call `response.raise_for_status()`. The existing `test_search_movie` test needed `mock_response.raise_for_status = Mock()` added to avoid `AttributeError`.
