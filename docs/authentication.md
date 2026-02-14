# Authentication System Documentation

As of February 2026, Cinelog Server has migrated from Firebase Authentication to a self-hosted solution. This document details the new authentication flow, security measures, and API usage.

## Overview

- **Protocol**: JWT (JSON Web Tokens)
- **Storage**: `HttpOnly`, `Secure`, `SameSite=Strict` Cookies (No LocalStorage/SessionStorage)
- **CSRF Protection**: Double Submit Cookie Pattern
- **Password Hashing**: bcrypt

## Authentication Flow

### Registration
**Endpoint**: `POST /v1/auth/register`

1.  Client sends user details (email, password, etc.).
2.  Server hashes password using `bcrypt`.
3.  Server creates user in MongoDB.
4.  Server issues two HttpOnly cookies:
    -   `access_token`: Short-lived (15 mins).
    -   `refresh_token`: Long-lived (7 days).
5.  Server sets a `csrf_token` cookie (HttpOnly=False) for CSRF protection.

### Login
**Endpoint**: `POST /v1/auth/login`

1.  Client sends email and password.
2.  Server verifies password hash.
3.  Server issues `access_token` and `refresh_token` cookies.
4.  Server sets `csrf_token` cookie.

### Accessing Protected Resources
**Middleware**: `app/dependencies/auth_dependency.py`

1.  Client makes a request to a protected route (e.g., `POST /v1/logs`).
2.  Browser automatically attaches `access_token` cookie.
3.  Server verifies the JWT signature and expiration.
    -   If valid: Request proceeds.
    -   If invalid/expired: Server returns `401 Unauthorized`.

### Token Refresh
**Endpoint**: `POST /v1/auth/refresh`

If the client receives a `401`, it should attempt to refresh the token:

1.  Client calls `/v1/auth/refresh`.
2.  Browser attaches the `refresh_token` cookie (scoped to `/v1/auth/refresh` if supported, otherwise global).
3.  Server verifies the refresh token.
4.  Server issues a new `access_token` (and rotates `refresh_token`).
5.  Client retries the original request.

### Logout
**Endpoint**: `POST /v1/auth/logout`

1.  Server clears `access_token` and `refresh_token` cookies.

---

## CSRF Protection (Double Submit Cookie)

Since we use cookies for authentication, we must protect against Cross-Site Request Forgery (CSRF).

### Mechanism
1.  **Cookie**: The server sets a `csrf_token` cookie (readable by JavaScript).
2.  **Header**: For every "unsafe" request (`POST`, `PUT`, `DELETE`, `PATCH`), the client **must** read the `csrf_token` cookie and send its value in the `X-CSRF-Token` header.
3.  **Validation**: The `CSRFMiddleware` verifies that the cookie value matches the header value.

### Implementation Details
-   **Safe Methods** (`GET`, `HEAD`, `OPTIONS`): Exempt from CSRF checks.
-   **Initial Token**: The token is set on `login` and `register`. If the client needs a token before logging in (e.g., for registration itself, although usually exempt or handled), or if the cookie is missing, call **`GET /v1/auth/csrf`**.

**Example (Frontend Logic):**
```javascript
// Get token from cookie
const csrfToken = getCookie("csrf_token");

// Attach to request
fetch("/v1/logs", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-CSRF-Token": csrfToken 
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
