# Movie Ratings API

**Last Updated:** 2026-10-31

Authenticated users rate catalog movies from 1 to 10, with an optional comment. A user has one rating per movie; rating a movie again replaces the score. Movies are identified by their Cinelog UUID. Search results that only carry a `movieRef` must be resolved first (see [Movie Search, Resolution and Details](tmdb-service.md)).

All endpoints require the `__Host-access_token` cookie. `POST` also requires `X-CSRF-Token`.

## Create or update a rating

```
POST /v1/movie-ratings/
X-CSRF-Token: <csrf>

{ "movieId": "6f1c2a9e-4b7d-4c1e-9a55-0d2b8f3e7a10", "rating": 8, "comment": "Great" }
```

**Response (200 OK):**

```json
{
  "id": "1d9a…",
  "userId": "a3b4…",
  "movieId": "6f1c2a9e-4b7d-4c1e-9a55-0d2b8f3e7a10",
  "rating": 8,
  "comment": "Great",
  "createdAt": "2026-10-31T10:00:00Z",
  "updatedAt": "2026-10-31T10:00:00Z"
}
```

| Status | When |
|--------|------|
| `200` | Rating created or updated |
| `404 MOVIE_NOT_FOUND` | `movieId` is unknown or the movie was removed from the catalog |
| `422` | Missing or malformed `movieId`, rating outside 1–10, or any extra field such as `tmdbId`, even alongside a valid `movieId` |

## Read your rating

```
GET /v1/movie-ratings/{movieId}
```

| Status | When |
|--------|------|
| `200` | Returns the rating shown above |
| `204 No Content` | The movie exists but you have not rated it |
| `404 MOVIE_NOT_FOUND` | Unknown or removed movie |
| `422` | `movieId` is not a UUID (including old numeric TMDB IDs) |

Ratings changed here also appear on all of your logs for the same movie. Ratings can also be set while creating or updating a log; see [Logs API](logs-api.md).

## See Also

- [Movie Search, Resolution and Details](tmdb-service.md)
- [Logs API](logs-api.md)
- [Technical: Canonical Movie Identity](../technical/movie-identity.md)
- [Technical: Atomic Log and Rating Writes](../technical/log-rating-writes.md)
