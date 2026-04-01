# Profile Visibility

Users can control who sees their profile and movie logs through a visibility setting.

## Visibility Levels

| Level | Profile Info | Movie Logs |
|---|---|---|
| `public` | Full (name, handle, bio, date of birth) | Accessible to all authenticated users |
| `friends_only` | Basic (name, handle, bio) — date of birth hidden | Hidden (same as private until friends system is built) |
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
  "profileVisibility": "public"
}
```

### Updating Visibility

Update visibility via the profile settings endpoint:

```json
PUT /v1/users/settings/profile
{
  "profileVisibility": "private"
}
```

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

Returns the user's movie logs if their profile is public or the requester is the profile owner. Returns **403** (`PROFILE_NOT_PUBLIC`) for private/friends-only profiles.

### Error Responses

| Status | Code | Description |
|---|---|---|
| 404 | `USER_NOT_FOUND` | User with given handle does not exist |
| 403 | `PROFILE_NOT_PUBLIC` | User's profile is not publicly visible |

## See Also

- [Technical: Profile Visibility](../technical/profile-visibility.md)
