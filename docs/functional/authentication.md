# Authentication

As of February 2026, Cinelog Server uses a self-hosted authentication solution (migrated from Firebase Authentication).

## Overview

- **Protocol**: JWT (JSON Web Tokens)
- **Token Storage**: Secure, HttpOnly cookies
- **CSRF Protection**: Double Submit Cookie Pattern

## Authentication Flow

### Registration
**Endpoint**: `POST /v1/auth/register`

1. Client sends user details (email, password, etc.).
2. Server creates the user and returns the newly created user details via JSON response.

*Note: Registration does not automatically log the user in. The client must make a subsequent call to `/v1/auth/login` to obtain authentication and CSRF cookies.*

### Login
**Endpoint**: `POST /v1/auth/login`

1. Client sends email and password.
2. Server verifies credentials.
3. Server issues two token cookies:
    - `__Host-access_token`: Short-lived (15 mins).
    - `refresh_token`: Long-lived (7 days), scoped to `/v1/auth/refresh`.
4. Server sets a `__Host-csrf_token` cookie and returns the CSRF token in the JSON response body.

### Accessing Protected Resources

1. Client makes a request to a protected route (e.g., `POST /v1/logs`).
2. Browser automatically attaches the `__Host-access_token` cookie.
3. Server verifies the token:
    - If valid: Request proceeds.
    - If invalid/expired: Server returns `401 Unauthorized`.

### Token Refresh
**Endpoint**: `POST /v1/auth/refresh`

If the client receives a `401`, it should attempt to refresh the token:

1. Client calls `/v1/auth/refresh`.
2. Browser automatically attaches the `refresh_token` cookie.
3. Server verifies the refresh token and issues new tokens (access + rotated refresh).
4. Client retries the original request.

### Logout
**Endpoint**: `POST /v1/auth/logout`

1. Server clears `__Host-access_token`, `refresh_token`, and `__Host-csrf_token` cookies.

---

## CSRF Protection

Since cookies are used for authentication, every "unsafe" request (`POST`, `PUT`, `DELETE`, `PATCH`) must include a CSRF token.

### How to use it

1. **Obtain the token**: The CSRF token is returned in the JSON response body on `login`, `register`, and `GET /v1/auth/csrf`.
2. **Send it back**: Include the token value in the `X-CSRF-Token` header on every mutation request.

**Example (Frontend):**
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

1. **Request Reset**: `POST /v1/auth/forgot-password` with `{ "email": "..." }`.
    - Server generates a 6-character code (valid for 15 minutes) and sends it via email.
2. **Reset Password**: `POST /v1/auth/reset-password` with `{ "email": "...", "code": "...", "new_password": "..." }`.
    - Server verifies code and updates the password.

---

## See Also

- [Technical Authentication Details](../technical/authentication.md) — Implementation internals, middleware, cookie configuration
