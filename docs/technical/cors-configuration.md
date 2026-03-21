# CORS Configuration

This guide explains how to configure CORS for Cinelog Server in development and production.

## Overview

The API uses an explicit allow list for CORS origins. In development, it falls back to localhost defaults if no origins are configured. In production, you should always set `CORS_ORIGINS`.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ORIGINS` | Production | - | Comma-separated list of allowed origins |
| `CORS_ALLOW_CREDENTIALS` | No | true | Allow credentials in CORS |
| `ENVIRONMENT` | No | development | Environment name |

Example `.env`:

```bash
# CORS Configuration
CORS_ORIGINS=https://cinelog.app,https://www.cinelog.app
CORS_ALLOW_CREDENTIALS=true
```

## How It Works

### Development Defaults

If `ENVIRONMENT=development` and `CORS_ORIGINS` is not set, the API allows:

- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

This keeps local frontend work convenient without needing extra setup.

### Production Behavior

In production, you should set `CORS_ORIGINS` explicitly. If it is not set, the API returns an empty allow list, so browsers will block cross-origin requests.

### Credentials

`CORS_ALLOW_CREDENTIALS` controls whether the API returns `Access-Control-Allow-Credentials: true`. Set it to `true` if your frontend needs cookies or authorization headers across origins. If you do not need credentialed requests, set it to `false` for a more restrictive posture.

## Configure For Docker Compose

Add the variables to your `.env` file, which is loaded by `docker-compose.local.yml`:

```bash
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
```

Restart the API container after updating the file.

## Configure For Vercel

Set the environment variables in the Vercel dashboard:

- `ENVIRONMENT=production`
- `CORS_ORIGINS=https://cinelog.app,https://www.cinelog.app`
- `CORS_ALLOW_CREDENTIALS=true`

## Verify With Curl

Allowed origin (expect `access-control-allow-origin`):

```bash
curl -i -X OPTIONS "http://127.0.0.1:5009/health" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET"
```

Disallowed origin (no `access-control-allow-origin`):

```bash
curl -i -X OPTIONS "http://127.0.0.1:5009/health" \
  -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: GET"
```
