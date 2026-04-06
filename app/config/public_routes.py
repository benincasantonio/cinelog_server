"""Centralized registry of public (unauthenticated) route paths."""

PUBLIC_AUTH_PATHS = frozenset(
    {
        "/v1/auth/register",
        "/v1/auth/login",
        "/v1/auth/forgot-password",
        "/v1/auth/reset-password",
    }
)

CSRF_EXEMPT_PATHS = PUBLIC_AUTH_PATHS | {
    "/v1/auth/refresh",
    "/docs",
    "/openapi.json",
}
