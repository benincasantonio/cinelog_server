# Authentication — Technical Details

This document covers the implementation internals of the Cinelog authentication system. For API usage and flows, see the [functional authentication doc](../functional/authentication.md).

## Security Stack

- **Password Hashing**: bcrypt
- **JWT Storage**: `HttpOnly`, `Secure`, `SameSite=Strict` cookies
- **CSRF**: Double Submit Cookie Pattern via `__Host-csrf_token`

## Password Length Validation

`NewPasswordStr` in `app/types/user_validation.py`, exported through `app.types`,
enforces 8–72 characters and at most 72 UTF-8 bytes for registration, reset, and
password-change new passwords. The validator returns the input unchanged and
uses a fixed error message without credential values. OpenAPI publishes the
character bounds and describes the additional byte limit. The existing validation
error handler sanitizes HTTP 422 responses before they reach clients.

Validation measures the submitted string before service-level normalization.
Registration and reset retain their existing `.strip()` calls; login and password
change continue to preserve whitespace. Normalization is not changed by this fix.

Bcrypt 5.0.0 raises `ValueError` for inputs over 72 bytes.
`PasswordService.verify_password` returns `False` for such inputs before calling
`bcrypt.checkpw`. Login and current-password checks therefore return their normal
invalid-password errors instead of HTTP 500. Valid-length passwords are verified
in full, without truncation or suffix equivalence. For example, 71 ASCII characters
followed by `é` encode to 73 bytes and cannot authenticate.

Hash creation remains untruncated, and bcrypt rejects oversized direct hashing
calls. Request validation prevents oversized new passwords from reaching hashing
or the password-change same-password comparison. Login and current-password
checks retain their existing schema constraints and share the bounded verifier.

Passwords exceeding 72 bytes are unsupported for both creation and verification.
There is no new hash format, automatic rehash, dependency change, or database migration.
See the [bcrypt 5.0.0 changelog](https://pypi.org/project/bcrypt/5.0.0/) for the
upstream length behavior change.

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
- **Token provisioning**: Tokens are set on `login` and `POST /v1/auth/refresh`. Clients can also call the authenticated `GET /v1/auth/csrf` endpoint to obtain a fresh token.

## Auth Endpoint Rate Limits

| Endpoint | Limit |
|----------|-------|
| `POST /v1/auth/register/send-code` | 6/hour per IP, plus 3/hour session and 5/30minute email-hash limits |
| `POST /v1/auth/register` | 10/hour per IP, plus 5/hour session |
| `POST /v1/auth/login` | 30 requests per 15 minutes per IP, plus session/email-hash limits |
| `POST /v1/auth/forgot-password` | 6 requests per hour per IP, plus 3/hour session and 5/30minute email-hash limits |
| `POST /v1/auth/reset-password` | 10 requests per hour per IP, plus session/email-hash limits |
| `GET /v1/auth/csrf` | 300 requests per 30 minutes per authenticated user |

The coarse IP and session limits are enforced via `slowapi` decorators in `app/controllers/auth_controller.py`. `AuthRateLimitService` handles the login and recovery email-hash buckets so they can be checked before authentication work and incremented only when the request should count.

## Registration Verification Implementation

- `POST /v1/auth/register/send-code` normalizes the submitted email and always returns a generic success response.
- If the email already has an account, `EmailService` sends an existing-account notice instead of issuing a code.
- If the email can be registered, `RegistrationVerificationService` generates a 6-character code, stores only an HMAC hash in Redis, and sends the plaintext code by email.
- Redis keys and stored code hashes are HMAC-derived using the dedicated `REGISTRATION_VERIFICATION_HMAC_SECRET` (separate from the rate-limiting secret) and use a 15-minute TTL. No verification-code table or migration is used.
- `POST /v1/auth/register` requires `verificationCode` and a supported full `locale` tag; the code must exist, be unexpired, match the email, and have fewer than 5 failed attempts.
- After successful account creation, the verification key is deleted so the code is single-use. If Redis loses the temporary key, the user must request a new code.

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

Registration verification emails use the same development fallback and log the registration code instead of sending through SMTP.

## See Also

- [Account Localization](localization.md) — Locale persistence, request resolution, and TMDB integration
- [Functional Authentication Doc](../functional/authentication.md) — API usage, flows, consumer guide
- [CORS Configuration](cors-configuration.md) — Related cross-origin settings
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — Codebase architecture reference
