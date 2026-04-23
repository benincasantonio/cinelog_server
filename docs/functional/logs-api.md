# Logs API

The viewing log endpoints let authenticated users record, update, list, and delete their own movie-watching history.

All endpoints are under `/v1/logs` and require a valid session:

- `__Host-access_token` cookie (JWT)
- `X-CSRF-Token` header matching the `__Host-csrf_token` cookie — required on `POST`, `PUT`, and `DELETE`

## Endpoints

| Method | Path | Purpose | Rate Limit |
|--------|------|---------|------------|
| `POST` | `/v1/logs/` | Create a new viewing log | 20 / minute |
| `PUT` | `/v1/logs/{log_id}` | Update an existing log the caller owns | 10 / minute |
| `DELETE` | `/v1/logs/{log_id}` | Delete an existing log the caller owns | 20 / minute |
| `GET` | `/v1/logs/{handle}` | List logs for a user by handle (respects profile visibility) | — |

## DELETE `/v1/logs/{log_id}`

Permanently removes a viewing log owned by the authenticated user. Deletion is a **hard delete** — the document is removed from the database and cannot be recovered. After success, the user's cached statistics are invalidated so the next stats read reflects the deletion.

### Request

```
DELETE /v1/logs/{log_id}
Cookie: __Host-access_token=<jwt>; __Host-csrf_token=<csrf>
X-CSRF-Token: <csrf>
```

No request body.

### Responses

| Status | When |
|--------|------|
| `204 No Content` | Log was deleted successfully. Response body is empty. |
| `401 Unauthorized` | No valid `__Host-access_token` cookie. |
| `403 Forbidden` | CSRF validation failed (missing or mismatched `X-CSRF-Token`). |
| `404 Not Found` | No log with `log_id` exists, or the log belongs to a different user. Both cases return the same `LOG_NOT_FOUND` error to avoid leaking existence. |
| `429 Too Many Requests` | Rate limit (20/min) exceeded. See [Rate Limiting](rate-limiting.md). |

### Example — 404 error body

```json
{
  "error_code_name": "LOG_NOT_FOUND",
  "error_code": 404,
  "error_message": "Log not found",
  "error_description": "The requested log entry was not found."
}
```

## See Also

- [Authentication](authentication.md) — cookie and CSRF setup
- [Rate Limiting](rate-limiting.md) — per-endpoint limits and 429 behavior
- [Stats Caching (technical)](../technical/stats-caching.md) — how log deletion invalidates cached stats
