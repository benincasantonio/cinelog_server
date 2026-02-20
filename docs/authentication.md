# Authentication System Documentation

As of February 2026, Cinelog Server has migrated from Firebase Authentication to a self-hosted solution. This document details the new authentication flow, security measures, and API usage.

## Overview

- **Protocol**: JWT (JSON Web Tokens)
- **Storage**: `HttpOnly`, `Secure`, `SameSite=Strict` Cookies (for tokens)
- **CSRF Protection**: Double Submit Cookie Pattern via `__Host-csrf_token`
- **Password Hashing**: bcrypt

## Authentication Flow

### Registration
**Endpoint**: `POST /v1/auth/register`

1.  Client sends user details (email, password, etc.).
2.  Server hashes password using `bcrypt`.
3.  Server creates user in MongoDB.
4.  Server returns the newly created user details via JSON response.

*Note: Registration does not automatically log the user in. The client must make a subsequent call to `/v1/auth/login` to obtain authentication and CSRF cookies.*

### Login
**Endpoint**: `POST /v1/auth/login`

1.  Client sends email and password.
2.  Server verifies password hash.
3.  Server issues two `HttpOnly` token cookies:
    -   `__Host-access_token`: Short-lived (15 mins), scoped to root (`/`).
    -   `refresh_token`: Long-lived (7 days), scoped to `/v1/auth/refresh`.
4.  Server sets a `__Host-csrf_token` cookie (`HttpOnly=True`) and returns the token in the JSON response body.

### Accessing Protected Resources
**Middleware**: `app/dependencies/auth_dependency.py`

1.  Client makes a request to a protected route (e.g., `POST /v1/logs`).
2.  Browser automatically attaches the `__Host-access_token` cookie.
3.  Server verifies the JWT signature and expiration.
    -   If valid: Request proceeds.
    -   If invalid/expired: Server returns `401 Unauthorized`.

### Token Refresh
**Endpoint**: `POST /v1/auth/refresh`

If the client receives a `401`, it should attempt to refresh the token:

1.  Client calls `/v1/auth/refresh`.
2.  Browser automatically attaches the `/v1/auth/refresh`-scoped `refresh_token` cookie.
3.  Server verifies the refresh token.
4.  Server issues a new `__Host-access_token` (and rotates `refresh_token`).
5.  Client retries the original request.

### Logout
**Endpoint**: `POST /v1/auth/logout`

1.  Server clears `__Host-access_token`, `refresh_token`, and `__Host-csrf_token` cookies.

---

## CSRF Protection (Double Submit Cookie)

Since we use cookies for authentication, we must protect against Cross-Site Request Forgery (CSRF).

### Mechanism
1.  **Cookie & Body**: The server sets a `__Host-csrf_token` cookie (`HttpOnly=True`) AND returns the token string in the JSON response body (e.g., during login or `/v1/auth/csrf`).
2.  **Header**: For every "unsafe" request (`POST`, `PUT`, `DELETE`, `PATCH`), the client **must** store the token from the previous JSON response and send its value in the `X-CSRF-Token` header.
3.  **Validation**: The `CSRFMiddleware` verifies that the `__Host-csrf_token` HttpOnly cookie value strictly matches the `X-CSRF-Token` header value.

### Implementation Details
-   **Safe Methods** (`GET`, `HEAD`, `OPTIONS`): Exempt from CSRF checks.
-   **Initial Token**: The token is set on `login` and `register`. If the client needs a token before logging in (e.g., for registration itself, although usually exempt or handled), or if the cookie is missing, call **`GET /v1/auth/csrf`**.

**Example (Frontend Logic):**
```javascript
// 1. Get token from login or /csrf response body
const loginResponse = await fetch("/v1/auth/login", { ... });
const { csrf_token } = await loginResponse.json();
// Store csrf_token in memory or state

// 2. Attach to subsequent mutation requests
fetch("/v1/logs", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-CSRF-Token": csrf_token 
  },
  body: JSON.stringify(data)
});
```

---

## Password Recovery

The password recovery flow replaces Firebase's email reset.

1.  **Request Reset**: `POST /v1/auth/forgot-password` with `{ "email": "..." }`.
    -   Server generates a 6-char code (valid for 15 mins).
    -   Server sends email via SMTP (configured in environment).
2.  **Reset Password**: `POST /v1/auth/reset-password` with `{ "email": "...", "code": "...", "new_password": "..." }`.
    -   Server verifies code.
    -   Server updates password hash.

---

## Local Development (Emails)

If `SMTP_SERVER` is not configured in `.env`, the server will **log the reset code to the console** instead of sending an email. This is useful for local development and testing.

Check your terminal output:
```text
--- EMAIL MOCK ---
To: user@example.com
Subject: Password Reset
Code: 123456
------------------
```
