# Redis Caching

This document covers the Redis caching layer in the Cinelog API.

## Configuration

Redis is **required** — the application will not start without a reachable Redis instance.

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_DEFAULT_TTL` | `300` | Default TTL in seconds (5 minutes) |

Configuration is read by `app/config/redis.py` and passed to `CacheService.initialize()` during app startup.

Rate-limited auth routes also require `RATE_LIMIT_HMAC_SECRET` so account-based limiter keys can be derived independently from JWT signing.

## CacheService Design

`CacheService` (`app/services/cache_service.py`) is a singleton that wraps `redis.asyncio` operations.

### Singleton Lifecycle

- **Initialization:** `CacheService.initialize(config)` is called during the FastAPI lifespan startup (in `app/__init__.py`)
- **Access:** `CacheService.get_instance()` returns the singleton — raises `RuntimeError` if not initialized
- **Shutdown:** `CacheService.aclose_all()` closes the Redis client and clears the singleton

### Methods

| Method | Return | Description |
|--------|--------|-------------|
| `get(key)` | `dict \| list \| None` | Retrieve and deserialize a cached value |
| `set(key, value, ttl?)` | `bool` | Serialize and store a value with TTL |
| `delete(key)` | `bool` | Delete a single cached key |
| `hgetall(key)` | `dict[str, str]` | Read a Redis hash |
| `hset_with_ttl(key, mapping, ttl)` | `int` | Store a hash with string field names, string or integer values, and a TTL atomically |
| `hincrby(key, field, amount?)` | `int` | Increment a numeric Redis hash field |
| `delete_many(keys)` | `int` | Bulk delete multiple keys |
| `invalidate_pattern(pattern)` | `int` | Delete all keys matching a glob pattern (uses `SCAN`) |
| `health_check()` | `bool` | Ping Redis to verify connectivity |
| `aclose()` | `None` | Close the Redis client and clear singleton |

### Error Behavior

`CacheService` is a low-level wrapper, so Redis errors propagate directly from its methods. Higher-level layers decide whether to fail open or fail closed.

`LogListCacheService` fails open: cache errors are logged and log lists fall back to PostgreSQL. Cache failures do not block log or rating writes.

`StatsCacheService`, `TMDBCacheService`, rate limiting, and registration verification do not catch Redis errors. The application fails fast on startup if Redis is unreachable, and these flows require Redis to remain healthy at runtime.

## Key Naming Convention

Cache keys follow the pattern: `cinelog:{entity}:{identifier}`

Examples:
- `cinelog:movie:550` — movie with TMDB ID 550
- `cinelog:log-list-response:v1:{user_id}:where:{watched_where}:from:{from}:to:{to}:sort:{sort_by}:{sort_order}` — complete filtered log-list response
- `cinelog:stats:{user_id}:all` — stats for a specific user
- `cinelog:notif:follow-started:{recipient_id}:{follower_id}` — rolling cooldown for `follow.started` emission

Key construction is the caller's responsibility — `CacheService` is key-agnostic.

## Cache Layer Boundaries

Cinelog uses cache layers at the same boundary as the data being cached:

- `*_cache_service.py` is for service-level, composed, or external API responses. `LogListCacheService` caches a complete `LogListResponse`; `StatsCacheService` and `TMDBCacheService` cache their respective responses.

Use the narrowest boundary that owns the data dependencies. If a response combines multiple repositories or services, caching it at that level also makes invalidation responsible for all of those dependencies.

`CacheService` itself is infrastructure. Domain cache layers use it through `CacheService.get_instance()` rather than inherit from it.

## Log List Response Cache

`LogListCacheService` stores the complete `LogListResponse` for each target user, filter, and sort combination. `LogService` checks profile visibility before reading the cache. A miss runs the PostgreSQL log/movie/rating join and caches the mapped response for the default five-minute TTL.

Successful log creation, update, deletion, and direct rating writes invalidate all response keys for the affected user. External movie-row changes are visible when the TTL expires. The former raw-log keys have a different prefix and expire naturally.

See [Log List Query](log-list-query.md) for the join and response semantics.

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
