# Movie Identity in Logs and Ratings

`movies` is the only owner of a movie's TMDB identity (`tmdb_id`) and poster (`poster_path`). Logs and ratings reference a movie through `movie_id`, and API responses derive `tmdbId` and `posterPath` from that movie. Ratings are unique per `(user_id, movie_id)`.

## Migration `009_drop_denormalized_columns`

Removes the MongoDB-era copies `logs.tmdb_id`, `logs.poster_path` and `movie_ratings.tmdb_id`, and replaces `uq_movie_ratings_user_tmdb` with `uq_movie_ratings_user_movie`.

**Pre-flight audit.** The upgrade stops before changing anything if a copied `tmdb_id` disagrees with its movie, or if a `(user_id, movie_id)` pair has more than one rating. The error lists each failed check with a count and sample ids; fix the data and re-run. Offline `--sql` scripts contain the same check as a `DO $$` block.

**Rollback.** The downgrade restores the columns and the old constraint, backfilling them from `movies`. Posters that clients had stored on logs, and that differed from the movie poster, cannot be restored.

## Soft-deleted movie identity

`ix_movies_tmdb_id` is unique across all rows, including soft-deleted ones. Logging or rating a TMDB id whose movie is soft-deleted returns `409 MOVIE_UNAVAILABLE`, and the deleted movie is not resurrected. No application path soft-deletes movies today; the long-term policy belongs to #248.

## See Also

- [Logs API](../functional/logs-api.md)
- [Atomic Log and Rating Writes](log-rating-writes.md)
- [Log List Query](log-list-query.md)
