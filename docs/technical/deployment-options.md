# Deployment Options

## Overview

Cinelog Server is a FastAPI application that can run anywhere an ASGI Python service can run. The repository does not require a specific hosting provider.

The recommended production path is a generic VPS or container host where the backend, Redis, and external PostgreSQL can be managed explicitly. Vercel is also a valid option for developers who want a free or low-friction deployment, but it is optional and self-managed.

## Generic VPS

A generic VPS is the preferred deployment model when you want full control over runtime, networking, logs, scaling, and service dependencies.

Typical setup:

- Build and run the API with `Dockerfile.prod`
- Start the stack with `docker-compose.prod.yml`
- Provide production environment variables through the host or deployment system
- Point `DATABASE_URL` at the external PostgreSQL database
- Run Redis either as a container in the stack or as a managed Redis service
- Put a reverse proxy such as Nginx, Caddy, or a cloud load balancer in front of the API
- Terminate TLS at the reverse proxy or load balancer

On `docker-compose.prod.yml` startup, Compose runs the `db-migrate` one-shot service before the API and the email worker:

```bash
alembic upgrade head
```

Both the `api` and `email-worker` services wait for that job to complete successfully, so failed PostgreSQL schema migrations block startup instead of allowing a partially migrated deployment.

The production container starts Uvicorn directly with the FastAPI app:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 5009 --workers 2
```

`email-worker` is a separate long-running container that delivers the durable outbound-message outbox (registration/reset emails and notification emails):

```bash
python worker.py
```

It has its `healthcheck` disabled in `docker-compose.prod.yml` — the image-level `HEALTHCHECK` in `Dockerfile.prod` curls `http://localhost:5009/`, which the worker does not serve. It has no Redis dependency and fails fast at startup if its email transport (`EMAIL_TRANSPORT`/`SMTP_SERVER`) is misconfigured. See [Outbound Email Delivery](outbound-email-delivery.md).

## Vercel

Vercel is a valid optional deployment target, especially for experimentation or free-tier hosting. It is not part of the default repository setup, so `vercel.json` is intentionally not committed as required project configuration.

If you choose Vercel, create the Vercel configuration in your own deployment branch or environment-specific setup.

Example optional `vercel.json`:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production"
  }
}
```

The backend exposes a generic ASGI application as `app.main:app`. This is not Vercel-specific; ASGI servers and hosting platforms can use the same entrypoint.

### This recipe alone does not deliver email

A Vercel deployment runs the API only. Since every outbound email — registration codes,
password resets, and notification mail — is written to the `outbound_messages` outbox and
sent by a separate long-running process, **an API-only deployment queues messages that
nobody ever delivers**, and users never receive their verification or reset codes.

Serverless platforms cannot host the worker: it is a continuously polling process holding
a PostgreSQL connection, not a request handler. If you deploy the API to Vercel, run the
worker somewhere that supports long-running processes — a small VPS container, a
`docker-compose.prod.yml` stack alongside it, or any always-on host — pointed at the same
`DATABASE_URL`:

```bash
python worker.py
```

Exactly one worker is not required (claims use `FOR UPDATE SKIP LOCKED`, so several can
run safely), but at least one must be running for any email to leave the system.

## Required Environment Variables

Production deployments should configure:

- `JWT_SECRET_KEY`
- `RATE_LIMIT_HMAC_SECRET`
- `REGISTRATION_VERIFICATION_HMAC_SECRET`
- `CURSOR_PAGINATION_HMAC_SECRET`
- `TMDB_API_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `CORS_ORIGINS`
- `CORS_ALLOW_CREDENTIALS`
- `ENVIRONMENT=production`

Email delivery (required by the worker, which refuses to start without a usable
transport; the API needs `DATABASE_URL` only, since it just enqueues):

- `EMAIL_TRANSPORT` — `smtp` in production; `console` prints instead of sending
- `SMTP_SERVER`, `SMTP_PORT`
- `SMTP_USER`, `SMTP_PASSWORD` — omit for an unauthenticated relay
- `SMTP_FROM_EMAIL`
- `SMTP_USE_SSL` — implicit TLS; also selected automatically on port 465
- `SMTP_TIMEOUT_SECONDS` — keep well below `OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS`

Optional Redis tuning:

- `REDIS_DEFAULT_TTL`

Optional worker tuning (defaults in `app/config/outbound_message_config.py`):

- `OUTBOUND_MESSAGE_BATCH_SIZE`
- `OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS`
- `OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS`
- `OUTBOUND_MESSAGE_MAX_RETRIES`
- `OUTBOUND_MESSAGE_RETRY_BASE_SECONDS`
- `OUTBOUND_MESSAGE_RETRY_MAX_SECONDS`
- `OUTBOUND_MESSAGE_RETRY_JITTER_RATIO`
- `OUTBOUND_MESSAGE_PURGE_INTERVAL_SECONDS`
- `OUTBOUND_MESSAGE_PURGE_BATCH_SIZE`
- `OUTBOUND_MESSAGE_DELIVERED_RETENTION_DAYS`
- `OUTBOUND_MESSAGE_FAILED_RETENTION_DAYS`
- `LOG_LEVEL`

## See Also

- [CORS Configuration](cors-configuration.md)
- [Postgres Migration](postgres-migration.md)
- [Redis Caching](redis-caching.md)
