# User Statistics API

The statistics endpoint summarizes the authenticated user's viewing history.

## Endpoint

```http
GET /v1/stats/me
GET /v1/stats/me?yearFrom=2023&yearTo=2024
```

Both year parameters are optional. When supplied, `yearFrom` starts at January 1 and `yearTo` ends at December 31, inclusive. Supplying `yearFrom` greater than `yearTo` returns `400 Bad Request`.

## Response fields

### Summary

| Field | Meaning |
|---|---|
| `totalWatches` | Number of viewing logs in the selected period |
| `uniqueTitles` | Number of distinct movies watched |
| `totalRewatches` | `totalWatches - uniqueTitles` |
| `totalMinutes` | Runtime summed once per watch; rewatches add runtime again |
| `voteAverage` | Average of the user's ratings for distinct watched titles, or `null` when none are rated |

Ratings are not weighted by rewatches. A movie watched multiple times contributes one rating to `voteAverage`.

### Distribution

`distribution.byMethod` counts logs in each supported viewing method:

- `cinema`
- `streaming`
- `homeVideo`
- `tv`
- `other`

### Pace

The `pace` object is reserved for a future pace calculation. Its current values are always:

```json
{
  "onTrackFor": 0,
  "currentAverage": 0.0,
  "daysSinceLastLog": 0
}
```

## Example response

```json
{
  "summary": {
    "totalWatches": 3,
    "uniqueTitles": 2,
    "totalRewatches": 1,
    "totalMinutes": 360,
    "voteAverage": 8.0
  },
  "distribution": {
    "byMethod": {
      "cinema": 1,
      "streaming": 1,
      "homeVideo": 1,
      "tv": 0,
      "other": 0
    }
  },
  "pace": {
    "onTrackFor": 0,
    "currentAverage": 0.0,
    "daysSinceLastLog": 0
  }
}
```

## See Also

- [Authentication](authentication.md)
- [Logs API](logs-api.md)
- [Statistics Query Implementation](../technical/stats-query.md)
- [Stats Caching](../technical/stats-caching.md)
