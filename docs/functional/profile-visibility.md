# Profile Visibility

Users can control who sees their profile and movie logs through a visibility setting.

## Visibility Levels

| Level | Profile Info | Movie Logs |
|---|---|---|
| `public` | Full (name, handle, bio, date of birth) | Accessible to all authenticated users |
| `followers_only` | Basic (name, handle, bio) — date of birth hidden | Hidden (same as private until follower authorization is built) |
| `private` | Basic (name, handle, bio) — date of birth hidden | Hidden |

**Note:** Email and password are never exposed to other users.

Own profile is always fully accessible regardless of visibility setting.

## Setting Visibility

### During Registration

`profileVisibility` is a required field when creating an account:

```json
POST /v1/auth/register
{
  "firstName": "John",
  "lastName": "Doe",
  "email": "john@example.com",
  "password": "securepassword123",
  "handle": "johndoe",
  "dateOfBirth": "1990-01-01",
  "profileVisibility": "followers_only"
}
```

### Updating Visibility

Update visibility via the profile settings endpoint:

```json
PUT /v1/users/settings/profile
{
  "profileVisibility": "followers_only"
}
```

## Coordinated Release

`followers_only` is a breaking replacement for `friends_only`; clients must not send the old value after this backend revision is deployed. Backend issue #195 and [cinelog_web#70](https://github.com/benincasantonio/cinelog_web/issues/70) therefore ship as one coordinated release.

Deploy the backend first so its automatic database migration completes, then deploy the matching frontend immediately afterward. If registration or profile settings must remain available without any temporary client/server mismatch, place those writes in a short maintenance or read-only window during the deployment.

Rollback also requires a maintenance window and coordinated old backend/frontend deployment. Operators must downgrade the database with the new backend image before restoring the old images; see the technical guide for the exact commands.

## Viewing Other Users' Profiles

### Get Profile by Handle

```
GET /v1/users/{handle}/profile
```

Returns a `UserProfileResponse` based on the target user's visibility setting. Authenticated users only.

### Get User's Logs by Handle

```
GET /v1/logs/{handle}
```

Returns the user's movie logs if their profile is public or the requester is the profile owner. Returns **403** (`PROFILE_NOT_PUBLIC`) for private/followers-only profiles.

### Error Responses

| Status | Code | Description |
|---|---|---|
| 404 | `USER_NOT_FOUND` | User with given handle does not exist |
| 403 | `PROFILE_NOT_PUBLIC` | User's profile is not publicly visible |

## See Also

- [Technical: Profile Visibility](../technical/profile-visibility.md)
