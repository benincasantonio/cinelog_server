# Movie Provider Mappings

Issue #248 separates external movie identity and provider observations from the
canonical movie. The UUID in `movies.id` and all log/rating references stay unchanged.

## Schema and identity

The `MovieProviderMapping` ORM model represents a stored link to an external
identity, distinct from the provider adapters in `app/providers/`. Its
`movie_providers` table has these columns:

| Column | Type | Meaning |
|---|---|---|
| `provider` | text | Allowlisted source name; currently `tmdb` |
| `external_id` | text | Opaque nonempty source identity |
| `movie_id` | UUID FK | Existing canonical `movies.id` |
| `payload` | nullable JSONB | Original validated provider snapshot |
| `last_synced_at` | nullable timestamptz | Acquisition time of the successfully persisted observation |

The primary key `(provider, external_id)` assigns each external identity to one
canonical film. `UNIQUE(movie_id, provider)` allows at most one identity from each
provider for a film, and its index supports lookups by movie UUID. **A film can have
multiple different providers**: there is no uniqueness constraint on `movie_id`
alone. No mapping UUID or independent soft-delete state is needed.

TMDB IDs are stored as strings such as `"550"`. A future provider can use UUID
strings or other identifiers without changing the column type. Adapters own source
format validation and normalization; storage does not cast IDs to numbers or UUIDs.
`MovieProviderName` in `app.types` defines enabled provider names for adapters,
services, repository validation and the model's database check. Migration revisions
freeze their own allowlists instead of importing this enum, so future application
changes cannot rewrite migration history. Enabling another provider requires
extending the enum, adding a migration for the database check and updating application
composition. This release enables only TMDB, without matching, aliases, provider
priorities or additional integrations.

Soft-deleting a movie preserves its mapping and reserves its external identity.
Active catalog reads filter the movie's state. Imports inspect deleted identities
and reject them with `409 MOVIE_UNAVAILABLE`, without provider calls, resurrection
or a new UUID. The foreign key also prevents physically deleting a referenced movie.
There is no independent mapping deletion API.

## Import and read behavior

`MovieRepository.find_movie_by_provider()` accepts a `MovieSourceReferenceDTO`,
bundling the provider name (`source`) and opaque `external_id`. Its `include_deleted`
option lets import inspect reserved identities; ordinary reads still return only
active movies. Existing service entry points accept numeric TMDB IDs and construct
this reference at the compatibility boundary.

The repository shares a private query builder between source lookup and conflict
recovery. Recovery executes that query in the same session after rollback and requires
the winning row to exist; ordinary lookup can return `None`. Queries explicitly
declare their provider loading with `selectinload`.

`create_movie()` flushes a new canonical movie, inserts the mapping with PostgreSQL
`ON CONFLICT ON CONSTRAINT pk_movie_providers DO NOTHING`, and commits both together.
If the mapping conflicts, it rolls back the whole transaction, including the
candidate movie, then reads the winning mapping and movie. Unrelated constraints
and persistence errors propagate; no candidate film is committed without its mapping.
Concurrent imports can make separate provider requests but converge on one UUID.

Retries return the persisted movie without changing its metadata, payload or
timestamp. A cached observation retains its acquisition time: data acquired at
10:00 and imported at 14:00 records 10:00, not 14:00. Migration, lookup, search and
cache reads never fabricate a successful synchronization time. No refresh policy
is introduced here; locale behavior and initial `en-US` imports remain unchanged.

`Movie.providers` uses `lazy="raise"`. Movie queries and the log-list query load
mappings explicitly with `selectinload`, before closing their session. List reads
batch these queries instead of issuing one per film. The temporary
`get_legacy_tmdb_id()` adapter selects the TMDB mapping and converts its ID for
numeric responses, with no database or provider calls. A missing mapping is an
invariant failure, never an inferred ID or a silently omitted history entry.
This adapter stays outside `Movie`; its model import is used only for type checking.

`movies` no longer has `tmdb_id`, `tmdb_payload` or `tmdb_last_synced_at`, including
Python compatibility properties. `movie_providers` is their sole source of truth.
Logs and ratings retain only their canonical movie foreign keys; existing response
fields derive TMDB identity from the mapping and posters from the movie. History
keeps numeric identity/posters even for a soft-deleted movie, with `movie: null`.

## Migration and rollback

Revision `010_create_movie_providers_table`, following
`009_drop_denormalized_columns`, copies every movie's integer TMDB ID to text,
payload and timestamp into one mapping before removing the original columns and
TMDB index. Deleted movies are included. UUIDs, other movie columns, ownership,
visibility, logs, ratings, authored notes/reviews and soft-delete fields are untouched.
SQL NULL payloads and timestamps remain NULL; the migration makes no network calls.

The downgrade recreates the columns, backfills from TMDB mappings, restores
`tmdb_id NOT NULL` and the unique `ix_movies_tmdb_id`, then removes the mapping table.
It refuses to run before any schema changes if there are:

- Movies without a TMDB mapping, including deleted movies.
- Additional providers whose data the old schema cannot store.
- IDs outside PostgreSQL's signed 32-bit integer range or in a noninteger format.
- IDs that collide after conversion or change their spelling, such as `"0550"`.

These guards also run in generated offline SQL. On refusal, investigate the data;
do not discard mappings or invent numeric IDs to force rollback. The original
schema cannot represent future arbitrary-string identities or multiple providers.

## Coordinated deployment runbook

This is a schema-breaking backend deployment with unchanged public API contracts.
Old API instances cannot run on the new schema. Do not use a rolling deployment
that leaves an old instance serving traffic during migration.

Revision 010 intentionally keeps no compatibility columns: it backfills mappings
and drops `tmdb_id`, `tmdb_payload` and `tmdb_last_synced_at` in one step. A staged
rollout would require the new release to dual-write those columns and a later
contract migration to drop them; this release accepts a short planned outage
instead.

1. Complete tests and inspect `make db-schema-migrate-dry-run`. Back up the target
   database and retain the previous backend artifact. Confirm its current revision
   is `009_drop_denormalized_columns` and build the new release before the outage
   (`make docker-build-prod` for the production Compose setup).
2. Drain traffic and stop every old API instance. For a single Compose deployment,
   use `docker compose -f docker-compose.prod.yml stop api`; there is no Make target
   for stopping only the API. Keep PostgreSQL available.
3. Deploy with `make docker-prod-up`. The existing `db-migrate` service upgrades
   before the new API starts. A failed migration must keep traffic closed; inspect
   the failure before restarting. For non-Compose deployment, apply with
   `make db-schema-migrate` using the release environment before starting the API.
4. Confirm the new revision and that every movie has exactly one TMDB mapping,
   including deleted rows. Check health, numeric movie details, existing diary
   reads and a log/rating write before reopening traffic. Confirm stable movie UUIDs.

To roll back this release, stop the new API first. Using the **new release's**
migration code and target database configuration, run `make db-schema-rollback`
only when the current revision is `010_create_movie_providers_table`. In a container,
the equivalent explicit command is
`docker compose -f docker-compose.prod.yml run --rm db-migrate alembic downgrade 009_drop_denormalized_columns`.
After a successful downgrade, deploy the retained old backend artifact and verify
the same numeric flows. If guards refuse rollback, keep the new schema and resolve
the incompatibility before switching code. Never start old code against revision 010.

No frontend deployment is needed for #248. Numeric endpoints and response fields
remain the compatibility surface. Their eventual removal belongs to #225 and is
gated on the relevant `cinelog_web` #97/#98 rollout; #99 owns later metadata/refresh
compatibility. Removing storage columns here does not remove these API contracts.

## Validation

PostgreSQL migration tests cover exact row preservation, online/offline round trips,
constraints, future provider cardinality and rollback refusal. Repository tests
cover race convergence with no orphan films, failed mapping rollback, original
observations, deleted identities and bounded batch loading. API tests cover unchanged
numeric shapes, multiple users, concurrent writes, provider failures and saved history.

The repository concurrency test holds the first import before commit and releases it
only after `pg_blocking_pids` confirms that PostgreSQL is blocking the second import
on the first transaction. It verifies the losing import's rollback, the shared UUID,
the winning metadata/observation and the absence of orphan movies. All waits have a
timeout and import tasks are cancelled and joined on failure. E2E tests separately
use a provider barrier to force both HTTP requests to miss the initial catalog lookup,
covering log+log and log+rating writes.

Run `make test-unit`, `make lint`, `make format-check`, `make typecheck`,
`make test-e2e` and `make db-schema-migrate-dry-run`.

## See Also

- [Functional: Movie Search and Details](../functional/tmdb-service.md)
- [Functional: Logs API](../functional/logs-api.md)
- [TMDB Movie Provider](tmdb-service.md)
- [Log List Query](log-list-query.md)
- [Postgres Migration](postgres-migration.md)
- [Deployment Options](deployment-options.md)
