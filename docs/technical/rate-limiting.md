# Rate Limiting

This document covers the rate limiting implementation in the Cinelog API.

## Overview

Rate limiting is enforced using [slowapi](https://github.com/laurents/slowapi), a FastAPI/Starlette-compatible wrapper around the `limits` library. Redis is used as the storage backend, ensuring limits are shared across all worker processes.

See Also: [Redis Caching](redis-caching.md)

## Limits

| Endpoint | Method | Limit |
|----------|--------|-------|
| `/v1/auth/register` | `POST` | 5 per hour per client |
| `/v1/auth/login` | `POST` | 30 per 15 minutes per IP, plus session/email-hash limits |
| `/v1/auth/forgot-password` | `POST` | 6 per hour per IP, plus 3 per hour per session and 5 per 30 minutes per email-hash account |
| `/v1/auth/reset-password` | `POST` | 10 per hour per IP, plus 10 per hour per session and 10 per hour per email-hash account for invalid credentials |
| `/v1/auth/csrf` | `GET` | 300 per 30 minutes per authenticated user |
| `/v1/movies/search` | `GET` | 20 per minute per client |
| `/v1/logs/` | `POST` | 20 per minute per client |
| `/v1/logs/{log_id}` | `PUT` | 10 per minute per client |

Rate limiting is applied per client using the key function described below.

## Implementation

### Limiter Setup (`app/config/rate_limiter.py`)

```python
from slowapi import Limiter
from app.utils.rate_limit_utils import get_rate_limit_key

limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=_redis_config["url"],
    headers_enabled=True,
    retry_after="delta-seconds",
)
```

- `key_func=get_rate_limit_key` — custom key function with fallback chain (see Client Identification below)
- `storage_uri` — points to the Redis instance (shared state across workers)
- `headers_enabled=True` — injects `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers on every response
- `retry_after="delta-seconds"` — sets the `Retry-After` header to seconds remaining until the limit resets

### Client Identification (`app/utils/rate_limit_utils.py`)

The `get_rate_limit_key` function determines the rate limit key for each request using a priority chain:

| Priority | Key Format | Source | When Used |
|----------|-----------|--------|-----------|
| 1st | `user:{user_id}` | `request.state.user_id` | Authenticated requests (set by `auth_dependency`) |
| 2nd | `ip:{address}` | Client IP via `get_remote_address` | Unauthenticated requests |

This ensures authenticated users are tracked by their user ID (consistent across IPs), while unauthenticated requests fall back to client IP by default. Specific endpoints can opt into additional session-scoped limits with a dedicated key function.

### Login Abuse Protection

`POST /v1/auth/login` uses a layered model:

1. A coarse outer IP limit enforced by `slowapi`
2. An anonymous session limit enforced by `slowapi`
3. An account limit enforced by `AuthRateLimitService` using a hashed normalized email

The email-based account limit behaves as follows:

- The limit key always uses a keyed HMAC hash of the normalized email
- The HMAC key comes from the required `RATE_LIMIT_HMAC_SECRET` environment variable
- No database lookup is needed to derive the key
- The bucket is checked before the login handler performs authentication work
- The bucket increments only after failed login attempts

Because the account layer is enforced outside `slowapi`, a login request can still return `429` without the `X-RateLimit-*` headers when the email-hash account protection triggers first.

### Password Recovery Abuse Protection

`POST /v1/auth/forgot-password` uses:

1. A coarse outer IP limit enforced by `slowapi` (`6/hour`)
2. An anonymous session limit enforced by `slowapi` (`3/hour`)
3. An email-hash account limit enforced by `AuthRateLimitService` (`5/30minute`)

`POST /v1/auth/reset-password` uses:

1. A coarse outer IP limit enforced by `slowapi` (`10/hour`)
2. An anonymous session limit enforced by `slowapi` (`10/hour`)
3. An email-hash account limit enforced by `AuthRateLimitService` (`10/hour`)

The recovery-route account buckets behave as follows:

- Keys always use a keyed HMAC hash of the normalized email
- The HMAC key comes from the required `RATE_LIMIT_HMAC_SECRET` environment variable
- No database lookup is needed to derive the bucket key
- `forgot-password` counts every request against the email-hash account bucket
- `reset-password` counts only invalid-credential attempts against the email-hash account bucket

For `forgot-password`, the account bucket is charged before the service call. That intentionally prevents repeated requests for a known email from bypassing the per-account cap, at the cost of a small denial-of-service window for that address if an attacker exhausts the `5/30minute` bucket first.

### Session Middleware (`app/middleware/rate_limit_session_middleware.py`)

`RateLimitSessionMiddleware` validates or sets a `__Host-session_id` cookie only for the public auth routes that use session-scoped limits: `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/forgot-password`, and `/v1/auth/reset-password`.

For those routes it:

1. Reuses the existing session only if it is present in Redis
2. Otherwise, generates a random session ID, stores it in Redis, and sets it as a `__Host-session_id` cookie

All other routes skip this work entirely, which avoids issuing unnecessary session cookies or decoding JWTs inside the middleware.

Cookie properties: `HttpOnly`, `Secure`, `SameSite=strict`, 7-day `max_age`.

### App Registration (`app/__init__.py`)

```python
from slowapi.errors import RateLimitExceeded
from app.config.rate_limiter import limiter
from app.utils.rate_limit_utils import rate_limit_exceeded_handler
from app.middleware.rate_limit_session_middleware import RateLimitSessionMiddleware

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(RateLimitSessionMiddleware)
```

The custom handler returns a structured `ErrorSchema` response (matching the format used by all other API errors) and preserves the `Retry-After` / `X-RateLimit-*` headers. See `app/utils/rate_limit_utils.py`.

### Endpoint Decoration

Each rate-limited endpoint must:

1. Accept `request: Request` as the **first positional parameter**
2. Accept `response: Response` as the **second positional parameter** (required for header injection)
3. Be decorated with `@limiter.limit("N/period")`

Example:

```python
@router.post("/register")
@limiter.limit("5/hour")
async def register(request: Request, response: Response, body: RegisterRequest = Body(...)):
    ...
```

## Response Headers

On every rate-limited response (both within limit and at 429), the following headers are present:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in the window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `Retry-After` | Seconds until the client may retry (only on 429) |

## 429 Response

When a client exceeds the limit, the API responds with:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1712345678
```

## Testing

Unit tests swap Redis for in-memory storage via an autouse fixture in `tests/units/conftest.py`:

```python
@pytest.fixture(autouse=True)
def use_memory_storage_for_rate_limiter():
    from limits.storage import MemoryStorage
    from limits.strategies import FixedWindowRateLimiter
    from app.config.rate_limiter import limiter

    original_storage = limiter._storage
    original_limiter = limiter._limiter

    mem = MemoryStorage()
    limiter._storage = mem
    limiter._limiter = FixedWindowRateLimiter(mem)

    yield

    limiter._storage = original_storage
    limiter._limiter = original_limiter
```

This ensures all unit tests run without a real Redis connection, and the in-memory state is reset after each test.

Rate limit behavior is tested in `tests/units/controllers/test_rate_limiting.py`.
