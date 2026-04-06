# Rate Limiting

The Cinelog API enforces rate limits on authentication and key data endpoints to protect against abuse and brute-force attacks.

## Limits

| Endpoint | Limit |
|----------|-------|
| `POST /v1/auth/register` | 5 requests per hour |
| `POST /v1/auth/login` | 30 requests per 15 minutes (outer IP limit) |
| `POST /v1/auth/forgot-password` | 6 requests per hour per IP, with tighter 3 per hour session and 5 per 30 minutes email-hash account limits |
| `POST /v1/auth/reset-password` | 10 requests per hour per IP, with matching 10 per hour session and invalid-credential account limits |
| `GET /v1/auth/csrf` | 300 requests per 30 minutes |
| `GET /v1/movies/search` | 20 requests per minute |
| `POST /v1/logs/` | 20 requests per minute |
| `PUT /v1/logs/{log_id}` | 10 requests per minute |

Some authentication endpoints apply multiple rate-limit layers. `POST /v1/auth/login`, `POST /v1/auth/forgot-password`, and `POST /v1/auth/reset-password` can also be blocked by anonymous-session or email-hash account buckets before the outer IP window is exhausted.

## Client Identification

Rate limits are applied per client, using the most specific identifier available:

| Priority | Identifier | When Used |
|----------|-----------|-----------|
| 1st | User ID | Authenticated requests (valid access token) |
| 2nd | Session ID | Unauthenticated requests with a `__Host-session_id` cookie |
| 3rd | IP address | Fallback when neither user ID nor session cookie is present |

### Session Cookie

When you call the public auth endpoints that use anonymous-session throttling (`register`, `login`, `forgot-password`, `reset-password`), the API automatically sets a `__Host-session_id` cookie on the response. This cookie:

- Is set once and reused for subsequent requests (7-day lifetime)
- Is `HttpOnly` and `Secure` — not accessible from JavaScript
- Provides more accurate per-client tracking than IP address alone (which can be shared behind NAT/proxies)

No action is needed from the client — the cookie is managed automatically.

## Rate Limit Headers

Every response from a rate-limited endpoint includes these headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in the current window |
| `X-RateLimit-Remaining` | Requests remaining before hitting the limit |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |

## When the Limit Is Exceeded

If you exceed the rate limit, the API responds with `429 Too Many Requests` and a structured error body:

```json
{
  "error_code_name": "RATE_LIMIT_EXCEEDED",
  "error_code": 429,
  "error_message": "Too many requests",
  "error_description": "You have exceeded the request limit. Please wait before trying again."
}
```

The `Retry-After` header tells you how many seconds to wait before retrying. Requests sent before that time will continue to receive `429`.

## See Also

- [Rate Limiting — Technical](../technical/rate-limiting.md)
