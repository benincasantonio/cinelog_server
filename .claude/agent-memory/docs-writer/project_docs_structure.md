---
name: docs structure
description: Location and classification of all documentation files after the functional/technical reorganization
type: project
---

docs/ is split into two subdirectories:

- docs/functional/ — user-facing, consumer-perspective docs
- docs/technical/ — developer-facing, infrastructure and implementation docs

Current files:
- docs/functional/authentication.md — JWT auth flow, CSRF usage, password recovery (API consumer perspective)
- docs/technical/cors-configuration.md — CORS env vars, Docker/Vercel setup
- docs/technical/e2e-testing.md — test setup, Docker MongoDB, CI secrets
- docs/technical/migrations.md — migration runner internals, writing migrations, CI/CD
- docs/technical/redis-caching.md — CacheService design, Docker setup, TTL strategy
- docs/technical/stats-caching.md — StatsCacheService, cache keys, invalidation triggers

docs/README.md is the top-level index with two sections: "Functional Docs" and "Technical Docs".

**Why:** Reorganized to separate user-facing docs from developer-facing docs per documentation architecture guidelines.
**How to apply:** When adding new docs, classify into functional/ or technical/ and update docs/README.md accordingly.
