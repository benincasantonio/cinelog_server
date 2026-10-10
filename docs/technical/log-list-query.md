# Log List Query

`GET /v1/logs/{handle}` checks profile visibility before reading the target user's log list. `LogService.get_user_logs()` uses `LogListCacheService` for the complete `LogListResponse`; on a miss, `LogRepository.find_logs_by_user_id()` reads PostgreSQL once.

The SQLAlchemy statement selects active logs, joins their movie (soft-deleted included, since it supplies `tmdbId` and `posterPath`), and outer-joins the owner's active rating on user and movie. Rewatches produce one row each with the same current rating. A soft-deleted movie or a missing rating appears as a `null` related field without removing the log. Date and viewing-location filters and the existing sort order apply to the log rows. `LogService` maps each row directly to an API item and computes watch/title/rewatch counts from the returned logs.

The response cache is keyed by target user, generation, filters, and sort order under `cinelog:log-list-response:v1:`. It uses `REDIS_DEFAULT_TTL` (five minutes by default). Successful log creation, update, deletion, and direct rating writes bump the user's `log-list` generation. An in-flight read always fills the generation it started with, so it cannot repopulate the cache used after an invalidation. Old generations expire with the response TTL. Redis read/write/invalidation failures are logged and do not block the database operation; if invalidation fails, a stale response can last until TTL expiry. Movie rows have no active update endpoint, so external movie-row changes also become visible at TTL expiry. The former raw-log cache keys and earlier response keys use different prefixes or shapes and expire without migration.

## See Also

- [Logs API](../functional/logs-api.md)
- [Redis Caching](redis-caching.md)
- [Atomic Log and Rating Writes](log-rating-writes.md)
