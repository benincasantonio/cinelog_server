"""Cinelog application package.

Intentionally empty. Python executes a package's ``__init__`` before any submodule, so
anything imported here is imported by every consumer of ``app.*`` — including the
outbound-message worker, which needs only PostgreSQL and SMTP settings. Building the
FastAPI application here therefore forced the worker to import every controller and to
supply every API secret (``JWT_SECRET_KEY``, the rate-limit, registration-verification
and cursor secrets, plus Redis configuration read at import time).

The ASGI application lives in ``app/api.py`` and is referenced as ``app.api:app``.
"""
