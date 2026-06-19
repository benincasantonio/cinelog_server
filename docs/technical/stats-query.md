# Statistics Query Implementation

`StatsRepository` is a read-only PostgreSQL repository that builds the user statistics read model across `logs`, `movies`, and `movie_ratings`. It does not have a corresponding ORM model or database table.

## Responsibilities

- `StatsRepository` owns SQL data retrieval and aggregation.
- `StatsService` converts year filters to inclusive dates, checks and writes the Redis cache, maps the aggregate into `StatsResponse`, and supplies the reserved zeroed pace object.
- `StatsCacheService` caches the final API response and remains independent from SQL data access.

## Query shape

The repository executes one SQLAlchemy statement:

1. A `filtered_logs` CTE selects the authenticated user's active logs and applies optional date bounds.
2. The main aggregate counts watches, distinct movie IDs, and each viewing method.
3. An outer join to active `movies` sums runtime per log. This intentionally counts runtime again for rewatches. Missing, deleted, or null-runtime movies contribute zero minutes.
4. A scalar rating aggregate filters active `movie_ratings` through a distinct movie-ID subquery over `filtered_logs`. This prevents rewatches from weighting ratings multiple times.

An empty rating set produces SQL `NULL`, which is returned as `voteAverage: null`.

## Filtering and deletion behavior

- Log date bounds use UTC start-of-day and end-of-day helpers and are inclusive.
- Soft-deleted logs are excluded from all statistics.
- Soft-deleted movies do not contribute runtime, while their active logs still count as watches.
- Soft-deleted ratings do not contribute to the average.
- Every aggregate is scoped to the requested user.

## No schema migration

The query uses existing columns and indexes. Adding `StatsRepository` requires no Alembic migration and creates no `stats` table.

## See Also

- [User Statistics API](../functional/stats-api.md)
- [Stats Caching](stats-caching.md)
- [Service Dependencies](service-dependencies.md)
