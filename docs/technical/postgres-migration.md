# PostgreSQL Migration Setup

## Scope

The current setup includes:

- SQLAlchemy asyncio, asyncpg, and Alembic dependencies
- Async PostgreSQL engine/session helpers in `app/db/postgres.py`
- Optional application startup initialization driven by `DATABASE_URL`
- Empty async Alembic scaffolding
- Local and e2e Docker Compose PostgreSQL services
- Deterministic Mongo ObjectId to PostgreSQL UUID conversion

## Environment

Set `DATABASE_URL` when you want the app or Alembic to initialize PostgreSQL:

```bash
DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5432/cinelog_db
```

The app still starts without `DATABASE_URL` while MongoDB repositories remain active. If the database backend is set to `postgres` through `DB_BACKEND`, startup raises a clear configuration error when `DATABASE_URL` is missing.

## Local Services

The local Docker stack includes PostgreSQL:

```bash
make docker-up
```

Local connection details:

| Field | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `cinelog_db` |
| User | `cinelog` |
| Password | `cinelog` |

The e2e compose file also includes PostgreSQL on host port `5433` with database `cinelog_e2e_db`.

## Schema Migrations

Alembic is initialized for async SQLAlchemy migrations, but no application table migrations are included in this setup.

Run migrations:

```bash
make db-schema-migrate
```

Roll back the latest migration:

```bash
make db-schema-rollback
```

## Deterministic IDs

During migration, PostgreSQL IDs derived from MongoDB documents must use the shared helper:

```python
from app.utils.id_utils import mongo_id_to_uuid

postgres_id = mongo_id_to_uuid("507f1f77bcf86cd799439011")
```

The helper uses UUID's built-in `NAMESPACE_URL` namespace. It maps only the Mongo ObjectId value, without including the collection name.

The same Mongo ObjectId always produces the same UUID, even when that ObjectId is referenced from another collection as a foreign key.

## Activation Guardrails

PostgreSQL repositories should only be activated through dependency wiring once their ID dependencies are ready. Public response IDs and JWT subjects should continue to use Mongo ObjectId strings until the core cutover has an explicit compatibility plan.

Do not switch a repository to PostgreSQL if an active MongoDB repository still needs to store or query IDs produced only by PostgreSQL.

## Later Tickets

Future migration tickets should add:

- SQLAlchemy table models
- Alembic migrations that create application tables and indexes
- PostgreSQL repository implementations
- Data migration runner and mapping/version tables
- Repository activation and rollback flags
