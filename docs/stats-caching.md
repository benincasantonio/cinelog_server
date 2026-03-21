# Stats Caching

This document covers the stats caching strategy implemented via `StatsCacheService`.

## Overview

User stats are expensive to compute — they aggregate data across logs and movie ratings. `StatsCacheService` wraps the low-level `CacheService` singleton to provide a domain-specific caching layer for stats, with automatic invalidation when underlying data changes.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `STATS_CACHE_TTL` | `259200` (3 days) | TTL in seconds for cached stats entries |

The TTL acts as a safety net. In practice, cache entries are invalidated on every write operation that affects stats, so entries rarely survive to expiration.

## Cache Key Structure

Keys follow the pattern: `cinelog:stats:{user_id}:{year_from}:{year_to}`

| Scenario | Key example |
|----------|-------------|
| No year filters | `cinelog:stats:{uid}:all` |
| Both years specified | `cinelog:stats:{uid}:2023:2024` |
| Only `year_from` | `cinelog:stats:{uid}:2023:any` |
| Only `year_to` | `cinelog:stats:{uid}:any:2024` |

Each combination of user and year filters produces a unique cache entry.

## Cache Flow

### Read path (`StatsService.get_user_stats`)

1. `StatsCacheService.get_stats()` checks Redis for a cached entry
2. On **hit**: returns the cached `StatsResponse` — no database queries needed
3. On **miss**: stats are computed from the database, then stored via `StatsCacheService.set_stats()`

### Write path (invalidation)

When data that affects stats is modified, all cached stats for that user are invalidated using `invalidate_user_stats(user_id)`, which calls `invalidate_pattern("cinelog:stats:{user_id}:*")` to clear every year-filter combination at once.

## Invalidation Triggers

| Service | Method | Trigger |
|---------|--------|---------|
| `LogService` | `create_log` | New viewing log created |
| `LogService` | `update_log` | Existing viewing log updated |
| `MovieRatingService` | `create_update_movie_rating` | Rating created or updated |

### Gap to be aware of

`LogRepository` has a `delete_log` method that is not currently exposed via any API endpoint. If a delete log endpoint is added in the future, it must also call `invalidate_user_stats`.

## Graceful Degradation

`StatsCacheService` inherits the graceful degradation behavior of `CacheService`:

- If Redis is unavailable or `CacheService` is not initialized, all methods return `None` or no-op
- Stats are computed from the database as a fallback
- No exceptions propagate to callers
