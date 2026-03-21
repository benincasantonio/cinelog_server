# Authentication — Technical Details

This document covers the implementation internals of the Cinelog authentication system. For API usage and flows, see the [functional authentication doc](../functional/authentication.md).

## Security Stack

- **Password Hashing**: bcrypt
- **JWT Storage**: `HttpOnly`, `Secure`, `SameSite=Strict` cookies
- **CSRF**: Double Submit Cookie Pattern via `__Host-csrf_token`

## Cookie Configuration

| Cookie | Scope | Lifetime | Flags |
|--------|-------|----------|-------|
| `__Host-access_token` | `/` (root) | 15 minutes | `HttpOnly`, `Secure`, `SameSite=Strict` |
| `refresh_token` | `/v1/auth/refresh` | 7 days | `HttpOnly`, `Secure`, `SameSite=Strict` |
| `__Host-csrf_token` | `/` (root) | Session | `HttpOnly`, `Secure`, `SameSite=Strict` |

The `__Host-` prefix ensures cookies are only sent over HTTPS and cannot be set by subdomains.

## Auth Middleware

**File**: `app/dependencies/auth_dependency.py`

The auth dependency extracts the `__Host-access_token` cookie, verifies the JWT signature and expiration, and injects the authenticated user into the request context.

## CSRF Middleware

**File**: `app/middleware/csrf_middleware.py` (CSRFMiddleware)

- **Safe methods** (`GET`, `HEAD`, `OPTIONS`): Exempt from CSRF checks.
- **Unsafe methods** (`POST`, `PUT`, `DELETE`, `PATCH`): The middleware verifies that the `__Host-csrf_token` HttpOnly cookie value strictly matches the `X-CSRF-Token` header value.
- **Token provisioning**: Tokens are set on `login` and `register`. Clients can also call `GET /v1/auth/csrf` to obtain a fresh token.

## Password Recovery Implementation

- Server generates a 6-character reset code (valid for 15 minutes).
- Code is sent via SMTP (configured through environment variables).
- Password is re-hashed with bcrypt on reset.

## Local Development (Emails)

If `SMTP_SERVER` is not configured in `.env`, the server logs the reset code to the console instead of sending an email:

```text
--- EMAIL MOCK ---
To: user@example.com
Subject: Password Reset
Code: 123456
------------------
```

## See Also

- [Functional Authentication Doc](../functional/authentication.md) — API usage, flows, consumer guide
- [CORS Configuration](cors-configuration.md) — Related cross-origin settings
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — Codebase architecture reference
