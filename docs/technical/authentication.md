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
- If the email already has an account, `AuthService` enqueues an existing-account notice instead of issuing a code, via `OutboundMessageService.enqueue_registration_existing_account()`.
- If the email can be registered, `RegistrationVerificationService` generates a 6-character code, stores only an HMAC hash in Redis, and `AuthService` enqueues the plaintext code for email delivery via `OutboundMessageService.enqueue_registration_verification()`.
- Redis keys and stored code hashes are HMAC-derived using the dedicated `REGISTRATION_VERIFICATION_HMAC_SECRET` (separate from the rate-limiting secret) and use a 15-minute TTL. No verification-code table or migration is used for *validation* — the code is never validated against a database row.
- The **rendered email**, however, does hold the plaintext code at rest until it is sent: durable delivery means the message body is stored in `outbound_messages` (see [Outbound Email Delivery](outbound-email-delivery.md)). The queued row carries the same 15-minute expiry as the code itself, its body is cleared the moment it reaches a terminal state, and reissuing a code cancels any still-queued predecessor. This is the trade made for not losing verification emails when SMTP fails.
- `POST /v1/auth/register` requires `verificationCode`; the code must exist, be unexpired, match the email, and have fewer than 5 failed attempts.
- After successful account creation, the verification key is deleted so the code is single-use. If Redis loses the temporary key, the user must request a new code.

`AuthService` no longer sends email directly — it enqueues onto the durable
`outbound_messages` outbox and returns; a dedicated worker process delivers the queued
message. See [Technical: Outbound Email Delivery](outbound-email-delivery.md) for the
full design (persistence, claim protocol, retry/backoff) and `AuthService`'s exact
cutover from the previous inline `EmailService` calls.

## Password Recovery Implementation

- Server generates a 6-character reset code (valid for 15 minutes).
- The code is enqueued for durable, asynchronous delivery by email — `AuthService.forgot_password()` calls `OutboundMessageService.enqueue_password_reset()` in a transaction separate from `set_reset_password_code()`; if the enqueue fails the request errors, so the client can retry rather than silently losing the code as the old inline-send design would.
- Password is re-hashed with bcrypt on reset.

## Local Development (Emails)

`EMAIL_TRANSPORT=console` (an explicit local-dev opt-in) makes the outbound-message
worker print instead of sending through SMTP:

```text
--- EMAIL (console transport) ---
To: user@example.com
Subject: Password Reset - Cinelog
Your password reset code is: 123456
This code will expire in 15 minutes.
----------------------------------
```

Registration verification and existing-account emails print through the same console
transport. With the default `EMAIL_TRANSPORT=smtp`, an unset `SMTP_SERVER` makes the
worker fail fast at startup (`RuntimeError`) instead of silently discarding mail — see
[Technical: Outbound Email Delivery](outbound-email-delivery.md).

## See Also

- [Functional Authentication Doc](../functional/authentication.md) — API usage, flows, consumer guide
- [Technical: Outbound Email Delivery](outbound-email-delivery.md) — the durable outbox, delivery worker, and `EMAIL_TRANSPORT`/`SMTP_*` configuration
- [CORS Configuration](cors-configuration.md) — Related cross-origin settings
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — Codebase architecture reference
