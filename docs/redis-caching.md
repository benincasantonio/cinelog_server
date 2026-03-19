# Redis Caching

This document covers the Redis caching layer in the Cinelog API.

## Configuration

Redis caching is controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_ENABLED` | `false` | Enable/disable the cache layer |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_DEFAULT_TTL` | `300` | Default TTL in seconds (5 minutes) |

Configuration is read by `app/config/redis.py` and passed to `CacheService.initialize()` during app startup.

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
| `aclose()` | `None` | Close the Redis client |

### Disabled Mode

When `REDIS_ENABLED=false`, `CacheService` is still initialized but all methods return immediately (`None`, `False`, or `0`) without making any Redis calls. This means callers don't need conditional logic.

## Key Naming Convention

Cache keys follow the pattern: `cinelog:{entity}:{identifier}`

Examples:
- `cinelog:movie:550` — movie with TMDB ID 550
- `cinelog:user:abc123:logs` — logs for a specific user
- `cinelog:stats:abc123` — stats for a specific user

Key construction is the caller's responsibility — `CacheService` is key-agnostic.

## TTL Strategy

- **Default TTL:** 300 seconds (5 minutes), configurable via `REDIS_DEFAULT_TTL`
- **Per-call TTL:** Callers can override the default by passing a `ttl` parameter to `set()`
- Frequently changing data (e.g., user stats) may use shorter TTLs
- Rarely changing data (e.g., movie details from TMDB) may use longer TTLs

## Graceful Degradation

Every `CacheService` method wraps Redis calls in try/except:

- On failure, errors are logged via `logger.exception()`
- Methods return safe defaults (`None`, `False`, `0`)
- The application continues to function without caching
- No exceptions propagate to callers

This design ensures Redis unavailability never causes API errors.

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
- API service has `REDIS_ENABLED=true` and `REDIS_URL=redis://redis:6379/0` set automatically

## Pattern Invalidation

`invalidate_pattern()` uses Redis `SCAN` (not `KEYS`) for production safety:

- `SCAN` is non-blocking and iterates incrementally
- `KEYS` blocks the Redis server and should not be used in production
- Matched keys are collected and deleted in a single `DELETE` call
