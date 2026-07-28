# Following — Technical

The first following implementation stores accepted directional edges for public targets. It intentionally does not
pre-build pending requests, status transitions, soft deletion, notifications, or follower-only authorization.

## Persistence

Alembic revision `007_create_user_follows_table` creates `user_follows`:

| Column | Purpose |
|---|---|
| `follower_id` | Active user initiating the directional relationship |
| `followed_id` | Target user |
| `created_at` | Database timestamp for edge creation |

`(follower_id, followed_id)` is the composite primary key and makes duplicate and concurrent PUT operations
idempotent. `ck_user_follows_not_self` prevents self-edges. Both user foreign keys use `ON DELETE CASCADE`, and
`ix_user_follows_followed_id` supports incoming follower counts; the primary-key order supports outgoing counts.
Unfollow operations hard-delete the edge.

Users are soft-deleted elsewhere in the application, so follow reads join the relevant user rows and apply
`User.active()`. Relationships involving inactive users are excluded from counts and requester-relative state.

## Layers and data flow

- `FollowRepository` performs conflict-safe inserts, idempotent deletes, active-edge checks, and profile aggregation.
- `FollowService` validates the authenticated follower, resolves target handles case-insensitively through
  `UserRepository`, rejects self-follows, and applies the public-target policy.
- `UserService.get_visible_profile` combines its existing visibility-aware profile mapping with a `FollowSummary`.
- `UserProfileResponse` serializes `follower_count`, `following_count`, and `is_following` as camelCase.
- `PUT` and `DELETE /v1/users/{handle}/follow` are authenticated, CSRF-protected, rate-limited endpoints returning
  `204 No Content`.

The profile aggregate is read in one database round trip using scalar count subqueries plus an existence check.

## Idempotency and visibility

For PUT, the service checks active relationship state before target visibility:

1. Validate the authenticated follower and resolve the active target.
2. Reject self-following.
3. Return successfully when an active edge already exists.
4. Reject a new edge unless the target is currently `public`.
5. Insert with `ON CONFLICT DO NOTHING`.

This ordering preserves retry behavior when a followed public target later becomes `private` or `followers_only`.
DELETE never applies a visibility check.

Profile visibility changes do not mutate relationship rows. Preserved relationships affect counts and `isFollowing`,
but existing profile/log authorization remains unchanged: `followers_only` still behaves like private for other users.

## Errors and rate limiting

The domain adds `SELF_FOLLOW_NOT_ALLOWED` (`400`) and reuses `USER_NOT_FOUND` (`404`) and `PROFILE_NOT_PUBLIC`
(`403`). Each mutation endpoint uses the existing authenticated-user SlowAPI key at `60/minute`, including the shared
structured `429 RATE_LIMIT_EXCEEDED` response and rate-limit headers.

## Verification

Coverage includes:

- model and Alembic constraint/index/cascade contracts;
- real-PostgreSQL repository idempotency, concurrency, directionality, active-user filtering, and aggregates;
- service policy and controller authentication/CSRF/error contracts;
- camelCase schema serialization;
- E2E follow, unfollow, mutual counts, non-public rejection, and visibility-transition behavior.

## See Also

- [Functional: Following](../functional/following.md)
- [Technical: Profile Visibility](profile-visibility.md)
- [Postgres Migration](postgres-migration.md)
