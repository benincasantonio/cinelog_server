# Profile Visibility — Technical

Implementation details for the user profile visibility feature.

## Data Model

The `User` model includes a `profile_visibility` column. API schemas expose it as `profileVisibility`:

```python
profile_visibility: Mapped[str] = mapped_column(
    Text,
    nullable=False,
    server_default=text("'private'"),
    default="private",
)
```

Valid values: `"public"`, `"followers_only"`, `"private"`.

The default is `"private"`.

## Validation

`ProfileVisibilityStr` is a reusable `Annotated` type in `app/types/user_validation.py`. It normalizes input (strip + lowercase) and validates against `PROFILE_VISIBILITY_CHOICES`. For optional fields, use `ProfileVisibilityStr | None` inline — do not create a separate `OptionalProfileVisibilityStr` alias.

`RegisterRequest`, `UpdateProfileRequest`, and `UserCreateRequest` all use this type, so application-level writes are limited to:

- `"public"`
- `"followers_only"`
- `"private"`

The PostgreSQL `users` table also enforces the same set with `CHECK (profile_visibility IN (...))`, so invalid values are rejected even if data bypasses Pydantic.

## API Endpoints

| Endpoint | Method | Visibility Check |
|---|---|---|
| `GET /v1/users/{handle}/profile` | Public profile lookup | Yes — strips `date_of_birth` for non-public profiles |
| `GET /v1/logs/{handle}` | User's logs | Yes — 403 for non-public/non-owner |
| `PUT /v1/users/settings/profile` | Update own profile | None (owner only, auth enforced) |
| `GET /v1/users/info` | Own info | None (owner only, auth enforced) |

The old `GET /v1/users/{user_id}/logs` endpoint has been replaced by `GET /v1/logs/{handle}`.

## Service Layer

`LogService` (in `app/services/log_service.py`) handles log retrieval with visibility checks:

- `get_user_logs_by_handle(handle, requester_id, request)` — looks up the user by handle, checks visibility (owner or public), then delegates to `get_user_logs()`. Raises `PROFILE_NOT_PUBLIC` for unauthorized access.

`UserService` (in `app/services/user_service.py`) has one visibility-aware method:

- `get_visible_profile(handle, requester_id)` — returns `UserProfileResponse`. Owner and public profiles get full data; private/followers-only profiles get `date_of_birth=None`.

Both services compare `str(user.id) == str(requester_id)` for ownership detection.

## Migration

Alembic revision `002_create_users_table` creates the column with a `private` server default and the original visibility constraint.

Revision `005_rename_profile_visibility` drops `ck_users_profile_visibility`, converts stored `friends_only` rows to `followers_only`, and recreates the constraint with the current values. Its downgrade reverses the conversion and restores the original constraint.

## Coordinated Deployment and Rollback

The backend change and [cinelog_web#70](https://github.com/benincasantonio/cinelog_web/issues/70) are intentionally incompatible with their previous wire values. Use the following release order:

1. Rehearse the migration against PostgreSQL before production:

   ```bash
   uv run pytest tests/units/db/test_profile_visibility_migration.py -v
   make db-schema-migrate-dry-run
   ```

2. If a temporary client/server mismatch is unacceptable, enable maintenance or read-only mode for registration and profile settings.
3. Deploy the new backend first. The production `db-migrate` service automatically runs `alembic upgrade head` before the API starts.
4. Confirm the deployed image and database revision:

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --no-deps db-migrate alembic current
   ```

   The revision must be `005_rename_profile_visibility`.

5. Run the database smoke checks through the managed PostgreSQL console or a direct, `psql`-compatible production DSN:

   ```bash
   psql "$POSTGRES_DSN" <<'SQL'
   SELECT profile_visibility, count(*)
   FROM users
   GROUP BY profile_visibility
   ORDER BY profile_visibility;

   SELECT pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conrelid = 'users'::regclass
     AND conname = 'ck_users_profile_visibility';
   SQL
   ```

   The data query must contain no `friends_only` rows, and the constraint must allow only `public`, `followers_only`, and `private`. `POSTGRES_DSN` refers to the same database as `DATABASE_URL` but uses a driver-neutral PostgreSQL URI accepted by `psql`.

6. With a smoke-test account, submit `profileVisibility: "followers_only"` through registration or `PUT /v1/users/settings/profile`; confirm the response returns `followers_only` and that `friends_only` receives `422`.
7. Deploy the matching frontend immediately, then disable maintenance/read-only mode.

Prefer roll-forward after revision `005` has reached production. If rollback is unavoidable:

1. Enable maintenance mode for registration and profile settings.
2. While the new backend image containing revision `005_rename_profile_visibility` is still deployed, downgrade explicitly:

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --no-deps db-migrate alembic downgrade 004_create_logs_table
   docker compose -f docker-compose.prod.yml run --rm --no-deps db-migrate alembic current
   ```

3. Confirm revision `004_create_logs_table`, verify rows were converted back to `friends_only`, and verify the restored check constraint.
4. Deploy the old backend and old frontend together, then disable maintenance mode.

Never deploy the old backend image before the downgrade: that image does not contain revision `005`, so its automatic migration job may be unable to resolve the database's current revision.

## Followers-Only Authorization Stub

`followers_only` currently behaves identically to `private`. A later epic ticket will grant accepted followers access by updating service-layer authorization; no further visibility-value rename will be required.

The basic following system accepts new relationships only when the target is public. Existing edges survive later
visibility changes and remain visible through profile counts and `isFollowing`, but they do not alter this authorization
stub. See the technical following guide for persistence and mutation behavior.

## See Also

- [Functional: Profile Visibility](../functional/profile-visibility.md)
- [Following](following.md)
- [Pydantic Types and Validators](pydantic_types_and_validators.md)
- [PostgreSQL Migration](postgres-migration.md)
