# Profile Visibility — Technical

Implementation details for the user profile visibility feature.

## Data Model

The `User` model includes a `profile_visibility` field (alias: `profileVisibility`):

```python
profile_visibility: str = Field(default="private", alias="profileVisibility")
```

Valid values: `"public"`, `"friends_only"`, `"private"`.

Default is `"private"` for existing users (set via migration 002).

## Validation

`ProfileVisibilityStr` is a reusable `Annotated` type in `app/types/user_validation.py`. It normalizes input (strip + lowercase) and validates against `PROFILE_VISIBILITY_CHOICES`. For optional fields, use `ProfileVisibilityStr | None` inline — do not create a separate `OptionalProfileVisibilityStr` alias.

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

- `get_visible_profile(handle, requester_id)` — returns `UserProfileResponse`. Owner and public profiles get full data; private/friends-only profiles get `date_of_birth=None`.

Both services compare `str(user.id) == str(requester_id)` for ownership detection.

## Migration

`migrations/002_add_profile_visibility.py` sets `profileVisibility: "private"` on all existing users missing the field. The `down()` function unsets it.

## Friends-Only Stub

`friends_only` is stored as a valid value but behaves identically to `private`. When a friends/follow system is implemented, the service layer checks can be updated without a schema or migration change.

## See Also

- [Functional: Profile Visibility](../functional/profile-visibility.md)
- [Pydantic Types and Validators](pydantic_types_and_validators.md)
- [Migrations](migrations.md)
