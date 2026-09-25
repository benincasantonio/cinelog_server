# Log List Query

`GET /v1/logs/{handle}` checks profile visibility before reading the target user's log list. `LogService.get_user_logs()` uses `LogListCacheService` for the complete `LogListResponse`; on a miss, `LogRepository.find_logs_by_user_id()` reads PostgreSQL once.

The SQLAlchemy statement selects active logs and outer-joins active movies and the owner's active movie ratings. The rating join matches the log's user, movie, and TMDB ID, so rewatches produce one row each with the same current rating. An absent or soft-deleted movie or rating leaves the log in the result with a `null` related field. Date and viewing-location filters and the existing sort order apply to the log rows. `LogService` maps each row directly to an API item and computes watch/title/rewatch counts from the returned logs.

The response cache is keyed by target user, filters, and sort order under `cinelog:log-list-response:v1:`. It uses `REDIS_DEFAULT_TTL` (five minutes by default). Successful log creation, update, deletion, and direct rating writes invalidate all list variants for that user. Redis read/write/invalidation failures are logged and do not block the database operation; if invalidation fails, a stale response can last until TTL expiry. Movie rows have no active update endpoint, so external movie-row changes also become visible at TTL expiry. The former raw-log cache keys use a different prefix and expire without migration.

## See Also

- [Logs API](../functional/logs-api.md)
- [Redis Caching](redis-caching.md)
- [Atomic Log and Rating Writes](log-rating-writes.md)
