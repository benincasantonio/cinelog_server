# Following

Authenticated users can create directional follow relationships with public profiles. A follow does not require the
target to follow back.

## Eligibility

| Follower visibility | Target visibility | New follow |
|---|---|---|
| Any | `public` | Allowed immediately |
| Any | `followers_only` | Rejected |
| Any | `private` | Rejected |

Follow requests and approvals are not supported. An existing relationship is preserved if the followed user later
changes away from `public`, but it does not grant access to restricted profile fields or movie logs.

## Follow a user

```http
PUT /v1/users/{handle}/follow
X-CSRF-Token: <token>
```

The endpoint requires authentication and a matching CSRF header/cookie pair. It returns `204 No Content`.

The operation is idempotent: following the same user again also returns `204` and does not create a duplicate
relationship. A preserved relationship can be retried after the target becomes non-public.

## Unfollow a user

```http
DELETE /v1/users/{handle}/follow
X-CSRF-Token: <token>
```

The endpoint returns `204 No Content`. Repeating it after the relationship is already absent is also successful.
Existing relationships can be removed regardless of the target's current visibility.

## Profile follow summary

`GET /v1/users/{handle}/profile` includes:

```json
{
  "followerCount": 12,
  "followingCount": 8,
  "isFollowing": true
}
```

- `followerCount` is the number of active users following the profile.
- `followingCount` is the number of active users the profile follows.
- `isFollowing` indicates whether the authenticated requester follows the profile owner.
- `isFollowing` is always `false` when viewing your own profile.

Counts are returned for public, followers-only, private, and own profiles. The endpoint does not expose the identities
behind those counts.

## Errors and rate limits

| Status | Code | Condition |
|---|---|---|
| `400` | `SELF_FOLLOW_NOT_ALLOWED` | The requester targets their own handle |
| `403` | `PROFILE_NOT_PUBLIC` | A new relationship targets a non-public profile |
| `404` | `USER_NOT_FOUND` | The follower account or target handle is inactive or missing |
| `429` | `RATE_LIMIT_EXCEEDED` | The requester exceeds 60 operations per minute on an endpoint |

## See Also

- [Technical: Following](../technical/following.md)
- [Profile Visibility](profile-visibility.md)
