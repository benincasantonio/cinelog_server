# Deployment Options

## Overview

Cinelog Server is a FastAPI application that can run anywhere an ASGI Python service can run. The repository does not require a specific hosting provider.

The recommended production path is a generic VPS or container host where the backend, Redis, and MongoDB connectivity can be managed explicitly. Vercel is also a valid option for developers who want a free or low-friction deployment, but it is optional and self-managed.

## Generic VPS

A generic VPS is the preferred deployment model when you want full control over runtime, networking, logs, scaling, and service dependencies.

Typical setup:

- Build and run the API with `Dockerfile.prod`
- Start the stack with `docker-compose.prod.yml`
- Provide production environment variables through the host or deployment system
- Point `MONGODB_URI` at a managed MongoDB instance or an externally managed MongoDB server
- Run Redis either as a container in the stack or as a managed Redis service
- Put a reverse proxy such as Nginx, Caddy, or a cloud load balancer in front of the API
- Terminate TLS at the reverse proxy or load balancer

The production container starts Uvicorn directly with the FastAPI app:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 5009 --workers 2
```

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

The backend exposes a generic ASGI application as `main:app`. This is not Vercel-specific; ASGI servers and hosting platforms can use the same entrypoint.

## Required Environment Variables

Production deployments should configure:

- `JWT_SECRET_KEY`
- `RATE_LIMIT_HMAC_SECRET`
- `TMDB_API_KEY`
- `MONGODB_URI`
- `REDIS_URL`
- `CORS_ORIGINS`
- `CORS_ALLOW_CREDENTIALS`
- `ENVIRONMENT=production`

Optional Redis tuning:

- `REDIS_DEFAULT_TTL`

## See Also

- [CORS Configuration](cors-configuration.md)
- [Redis Caching](redis-caching.md)
- [Migrations](migrations.md)
