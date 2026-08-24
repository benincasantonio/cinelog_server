# Atomic Log and Rating Writes

The log create and update APIs can change a viewing log and the authenticated user's movie-level score in one request. `LogService` resolves the movie as usual, then delegates the database write to the cache-decorated `LogRepository`.

## Transaction boundary

`LogRepository.create_log()` and `LogRepository.update_log()` use one SQLAlchemy session for the log mutation and optional movie-rating upsert. They commit once after both statements succeed. An exception from either statement closes the session without committing, so PostgreSQL rolls back both changes.

The shared `execute_movie_rating_upsert()` repository primitive does not commit. This lets the direct movie-rating repository retain its existing transaction while log writes include the same upsert in their own transaction.

## Rating behavior

- A non-null score upserts the row identified by `(user_id, tmdb_id)` and revives a soft-deleted row.
- Log requests never accept rating comments or reviews.
- Updating an active row through a log preserves its existing text.
- Reviving a deleted row through a log clears its old text so deleted user content is not restored.
- Omitted or null scores skip the rating statement entirely.
- An update first verifies log ownership; a missing or foreign log cannot alter a rating.

## Cache invalidation

The `LogCacheRepository` invalidates the owner log key plus affected user/movie list keys only after the inner repository returns from its successful commit. `LogService` then invalidates the user's cached statistics once. A failed database transaction reaches neither invalidation step.

## See Also

- [Logs API](../functional/logs-api.md)
- [Redis Caching](redis-caching.md)
- [Stats Caching](stats-caching.md)
