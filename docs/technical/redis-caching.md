# Redis Caching

This document covers the Redis caching layer in the Cinelog API.

## Configuration

Redis is **required** — the application will not start without a reachable Redis instance.

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_DEFAULT_TTL` | `300` | Default TTL in seconds (5 minutes) |
| `LOG_CACHE_TTL` | `86400` | TTL in seconds for cached log repository lookups |

Configuration is read by `app/config/redis.py` and passed to `CacheService.initialize()` during app startup.

Rate-limited auth routes also require `RATE_LIMIT_HMAC_SECRET` so account-based limiter keys can be derived independently from JWT signing.

## CacheService Design

`CacheService` (`app/services/cache_service.py`) is a singleton that wraps `redis.asyncio` operations.

### Singleton Lifecycle

- **Initialization:** `CacheService.initialize(config)` is called during the FastAPI lifespan startup (in `app/__init__.py`), after Beanie initialization
- **Access:** `CacheService.get_instance()` returns the singleton — raises `RuntimeError` if not initialized
- **Shutdown:** `CacheService.aclose_all()` closes the Redis client and clears the singleton

### Methods

| Method | Return | Description |
|--------|--------|-------------|
| `get(key)` | `dict \| list \| None` | Retrieve and deserialize a cached value |
| `set(key, value, ttl?)` | `bool` | Serialize and store a value with TTL |
| `delete(key)` | `bool` | Delete a single cached key |
| `delete_many(keys)` | `int` | Bulk delete multiple keys |
| `invalidate_pattern(pattern)` | `int` | Delete all keys matching a glob pattern (uses `SCAN`) |
| `health_check()` | `bool` | Ping Redis to verify connectivity |
| `aclose()` | `None` | Close the Redis client and clear singleton |

### Error Behavior

`CacheService` is a low-level wrapper, so Redis errors propagate directly from its methods. Higher-level cache layers decide whether to fail open or fail closed.

`LogCacheRepository` fails open: cache errors are logged and the repository falls back to the database query. This keeps log create, update, delete, and lookup flows available when Redis is temporarily unavailable.

## Key Naming Convention

Cache keys follow the pattern: `cinelog:{entity}:{identifier}`

Examples:
- `cinelog:movie:550` — movie with TMDB ID 550
- `cinelog:logs:id:{user_id}:{log_id}` — one log by ID, scoped to its owner
- `cinelog:logs:user:{user_id}:where:{watched_where}:from:{from}:to:{to}:sort:{sort_by}:{sort_order}` — filtered user logs
- `cinelog:logs:movie:{movie_id}:user:{user_id_or_all}` — logs for a movie, optionally scoped to a user
- `cinelog:stats:{user_id}:all` — stats for a specific user

Key construction is the caller's responsibility — `CacheService` is key-agnostic.

## Cache Layer Boundaries

Cinelog uses cache layers at the same boundary as the data being cached:

- `*_cache_service.py` is for service-level, composed, or external API responses. Examples: `StatsCacheService` caches a `StatsResponse`, and `TMDBCacheService` caches TMDB API responses.
- `*_cache_repository.py` is for raw persistence lookups. `LogCacheRepository` wraps a `LogRepository` instance and caches raw `Log` documents before `LogService` enriches them with movie and rating data.

Use the narrowest boundary that owns the data dependencies. If a response combines multiple repositories or services, caching it at that level also makes invalidation responsible for all of those dependencies.

### Composition over Inheritance

Repository cache decorators use composition. `LogCacheRepository` wraps a `LogRepository` instance via constructor injection, exposes the same method surface, and can be used anywhere a log repository dependency is expected.

Use composition when the cache layer is only a helper for storing, reading, or invalidating cached payloads. `StatsService` composes `StatsCacheService`, and `TMDBService` composes `TMDBCacheService`; those cache services are not substitutes for the full service APIs.

`CacheService` itself is infrastructure. Domain cache layers should use it through `CacheService.get_instance()` rather than inherit from it.

## Log Repository Cache

`LogCacheRepository` (`app/repository/log_cache_repository.py`) decorates a `LogRepository` instance and caches:

- `find_log_by_id(log_id, user_id)`
- `find_logs_by_user_id(...)`
- `find_logs_by_movie_id(movie_id, user_id?)`

Log repository cache entries default to a one-day TTL. Explicit invalidation on writes is the primary freshness mechanism; the TTL is a safety net for entries that are not touched by a write path.

Writes invalidate affected log cache entries:

| Method | Invalidation |
|--------|--------------|
| `create_log` | User log-list keys and movie log-list keys |
| `update_log` | Owner-scoped log ID key, user log-list keys, and movie log-list keys |
| `delete_log` | Owner-scoped log ID key, user log-list keys, and movie log-list keys after successful delete |

## TTL Strategy

- **Default TTL:** 300 seconds (5 minutes), configurable via `REDIS_DEFAULT_TTL`
- **Per-call TTL:** Callers can override the default by passing a `ttl` parameter to `set()`
- Frequently changing data (e.g., user stats) may use shorter TTLs
- Rarely changing data (e.g., movie details from TMDB) may use longer TTLs

## Serialization

`CacheService` is model-agnostic — it stores and retrieves raw JSON:

- **Writing:** Callers serialize Pydantic models with `model.model_dump(mode="json")` before calling `set()`
- **Reading:** Callers deserialize with `Model.model_validate()` after calling `get()`
- **Internal format:** Values are stored as JSON strings via `json.dumps()`/`json.loads()`

## Docker Setup

The local Docker Compose stack (`docker-compose.local.yml`) includes a Redis service:

- Image: `redis:7-alpine`
- Port: `6379`
- Health check: `redis-cli ping`
- Data persisted in `redis_data` volume
- API service connects via `REDIS_URL=redis://redis:6379/0`

Redis is also used as the backend for rate limiting via `slowapi`. See [Rate Limiting](rate-limiting.md).

## Pattern Invalidation

`invalidate_pattern()` uses Redis `SCAN` (not `KEYS`) for production safety:

- `SCAN` is non-blocking and iterates incrementally
- `KEYS` blocks the Redis server and should not be used in production
- Matched keys are collected and deleted in a single `DELETE` call
