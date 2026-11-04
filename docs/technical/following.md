# Following — Technical

The first following implementation stores accepted directional edges for public targets. It intentionally does not
pre-build pending requests, status transitions, soft deletion, or follower-only authorization. A successful new
follow emits a `follow.started` in-app notification; see [Notification Architecture](notifications.md).

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
  `UserRepository`, rejects self-follows, applies the public-target policy, and owns the transaction for the new edge
  and its required `follow.started` notification through `FollowRepository` and `NotificationRepository`.
- `UserService.get_visible_profile` combines its existing visibility-aware profile mapping with a `FollowSummary`.
- `UserProfileResponse` serializes `follower_count`, `following_count`, and `is_following` as camelCase.
- `PUT` and `DELETE /v1/users/{handle}/follow` are authenticated, CSRF-protected, rate-limited endpoints returning
  `204 No Content`.

`FollowService` opens a request-local `AsyncSession` and `session.begin()` around the follow insert, notification
history check, and notification insert. The context is the sole commit/rollback owner. The two repository creation
methods accept an optional session: supplied sessions are never committed, rolled back, or closed by repositories;
standalone calls still own their transaction. Unfollow and unrelated repository operations retain their behavior.
Cached service/repository instances hold providers, never a live session. Future follow-request transitions can use
the same explicit session boundary without introducing a generic unit-of-work layer.

`create_follow` uses `ON CONFLICT DO NOTHING RETURNING` and returns whether it inserted the edge. Only the winner
checks history and creates a notification. The composite primary key serializes competing inserts until commit;
the subsequent history query uses a fresh Read Committed snapshot. Concurrent losers do not notify. Existing edges
return before insertion and never backfill a missing notification, including after the target becomes non-public.

Notification suppression uses retained PostgreSQL history for the same recipient, actor, and `follow.started` type,
including read and soft-deleted rows. A timestamp strictly newer than the transaction's `now() - 604800 seconds`
suppresses another notification; exactly seven days qualifies. Suppressed attempts do not change any timestamps.
No Redis read/write or ISO-week key participates in this workflow. See [Notification Architecture](notifications.md).

Write and commit exceptions are logged and mapped to `500 ERROR_CREATING_FOLLOW` after transaction cleanup.
A rejected commit leaves neither new row. A connection loss during commit can leave the outcome unknown, but
PostgreSQL still stores both or neither; clients can retry without duplicating activity. The internal service returns
`NotificationCreateResult | None` only after successful commit (`None` means intentional suppression). The controller
ignores this internal result and returns `204`. No external publication occurs.

The profile aggregate is read in one database round trip using scalar count subqueries plus an existence check.

## Idempotency and visibility

For PUT, the service checks active relationship state before target visibility:

1. Validate the authenticated follower and resolve the active target.
2. Reject self-following.
3. Return successfully when an active edge already exists.
4. Reject a new edge unless the target is currently `public`.
5. Insert with `ON CONFLICT DO NOTHING RETURNING`; the winner checks history and writes any required inbox row.
6. Commit both writes before returning success.

This ordering preserves retry behavior when a followed public target later becomes `private` or `followers_only`.
DELETE never applies a visibility check.

Profile visibility changes do not mutate relationship rows. Preserved relationships affect counts and `isFollowing`,
but existing profile/log authorization remains unchanged: `followers_only` still behaves like private for other users.

## Errors and rate limiting

The domain adds `SELF_FOLLOW_NOT_ALLOWED` (`400`) and reuses `USER_NOT_FOUND` (`404`) and `PROFILE_NOT_PUBLIC`
(`403`). Failed follow persistence returns `ERROR_CREATING_FOLLOW` (`500`). Each mutation endpoint uses the existing authenticated-user SlowAPI key at `60/minute`, including the shared
structured `429 RATE_LIMIT_EXCEEDED` response and rate-limit headers.

## Verification

Coverage includes:

- model and Alembic constraint/index/cascade contracts;
- real-PostgreSQL repository idempotency, concurrency, directionality, active-user filtering, and aggregates;
- service policy and controller authentication/CSRF/error contracts;
- camelCase schema serialization;
- E2E follow, unfollow, mutual counts, non-public rejection, visibility-transition behavior, and follow.started
  inbox emission, Redis-independent rolling cooldown, exact seven-day boundaries, and structured write failures;
- real-PostgreSQL write/commit rollback, safe retry, simultaneous follows/refollows, and overlapping unfollow;
- migration upgrade/downgrade preserves all notification history.

## See Also

- [Functional: Following](../functional/following.md)
- [Technical: Notification Architecture](notifications.md)
- [Technical: Profile Visibility](profile-visibility.md)
- [Postgres Migration](postgres-migration.md)
