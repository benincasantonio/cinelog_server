# Notification Architecture

The notification subsystem stores reusable presentation/history records while requiring every notification domain and action to be registered explicitly. It deliberately has no arbitrary JSON metadata or polymorphic resource identifiers.

## Persistence Model

Alembic revision `006_create_notifications_table` creates `notifications` with:

| Column | Purpose |
|---|---|
| `id` | PostgreSQL-generated UUID primary key |
| `recipient_id` | Required user FK; hard deletion cascades the inbox rows |
| `actor_id` | Optional user FK; hard deletion sets it to `NULL` |
| `type` | Text constrained to registered `NotificationType` values |
| `title`, `body` | Rendered English presentation text |
| `deduplication_key` | Optional producer event key |
| `read_at` | Nullable server-owned read timestamp |
| shared fields | Soft deletion plus created/updated timestamps |

The active deduplication index is unique on `(recipient_id, deduplication_key)` where `deleted IS FALSE` and the key is non-null. Retried or concurrent creation returns the existing row with `created=False`; different recipients may use the same event key, null keys may repeat, and a soft-deleted key may be reused.

Active chronology uses `(recipient_id, created_at DESC, id DESC)`. A matching partial unread index adds `read_at IS NULL`. The UUID tie-breaker makes pagination deterministic when timestamps match.

## Closed Types and Schemas

`app/types/notification_types.py` is the single application source for:

- `NotificationType(StrEnum)`: `follow.started`, `follow.requested`, and `follow.accepted`.
- `NotificationAction(StrEnum)`: follow-request accept and reject actions.

Schemas import these enums from `app.types`; services do not repeat raw action strings. `NotificationBaseResponse`, `NotificationListResponse`, and `MarkAllNotificationsReadResponse` reject extra fields and inherit the application's camelCase aliases.

The generic response always includes `availableActions: []`. The registered action enum exists now so later follow-domain adapters can return authorized enum members without changing the common wire type.

## Repository and Read Semantics

`NotificationRepository` owns recipient scoping and database timestamps:

- Creation uses PostgreSQL conflict handling for concurrency-safe idempotency. `created_at` and `updated_at` are set from PostgreSQL `now()` rather than `BaseEntity`'s Python-side default, so inbox seek ordering does not depend on individual API instances agreeing on the wall clock.
- Listing fetches `limit + 1`, batch-loads actors with `selectinload`, and runs a separate recipient-wide unread count. Page query count is fixed rather than proportional to items.
- Individual read uses an update guarded by `read_at IS NULL`, then reloads the owned active row. A repeated call therefore preserves the first timestamp.
- Bulk read updates only active unread recipient rows with PostgreSQL `now()` and counts unread rows afterward in the same transaction.

Soft-deleted actor rows remain foreign-keyed for history but response assembly suppresses their user summary. Notification reads do not call or mutate any domain repository.

## Cursor Contract

The notification list uses the reusable `TimestampUUIDCursor` from `app/types/cursor_pagination_types.py`. The format version lives in `app/config/cursor_pagination_config.py`, which stays free of per-domain constants; the notification scope lives in `app/config/notification_config.py`, and `app/utils/cursor_pagination_utils.py` owns encoding and decoding. The token contains two unpadded Base64 URL-safe segments: a closed, versioned payload (`v`, `scope`, UTC `timestamp`, and UUID `id`) and an HMAC-SHA256 signature. The signature uses the dedicated `CURSOR_PAGINATION_HMAC_SECRET`; JWT, rate-limit, and registration-verification secrets are never reused.

Scopes are recipient-bound: `notification_list_cursor_scope()` returns `notifications.list:{recipient_id}`, so a cursor signed for one user fails verification for every other user. The raw prefix is private to that module, which makes the helper the only way to obtain a scope and prevents an unbound cursor from being signed by mistake.

Cursor verification happens once, in `NotificationService`, because the service is the only layer that knows the authenticated recipient the cursor must be bound to. `NotificationListRequest` therefore treats `cursor` as an opaque string with a length bound and performs no signature work, keeping the schema layer free of crypto and the signing secret. Rejection raises `AppException(ErrorCodes.INVALID_PAGINATION_CURSOR)` so failures use the application's structured error body rather than FastAPI's validation shape.

Clients must treat the cursor as opaque. Decoding verifies the signature with a timing-safe comparison before validating the exact payload shape, scope, version, timezone-aware timestamp, and UUID. A modified signature, wrong scope/recipient/version, or malformed payload returns HTTP 422 `INVALID_PAGINATION_CURSOR`. Rotating `CURSOR_PAGINATION_HMAC_SECRET` invalidates previously issued cursors, which clients must handle by restarting pagination. The seek predicate is:

```text
created_at < cursor.timestamp
OR (created_at = cursor.timestamp AND id < cursor.id)
```

## Channel Delivery

Creating a notification and enqueuing its outbound deliveries happen in one
transaction, via `NotificationUnitOfWork.create_notification_with_deliveries()`
(`app/repository/notification_unit_of_work.py`). `NotificationService.create_notification()`
delegates to it with the default channel set (`channels=(OutboundMessageChannel.EMAIL,)`).

The transaction seam is `RepositoryBase._unit_of_work(session=None)`: it opens and
commits its own session when called with no session (unchanged single-repository
behavior), or joins a caller-supplied session and leaves the commit to the caller.
`NotificationRepository.create_notification()` now accepts an optional keyword-only
`session=` for exactly this reason — existing callers that omit it are unaffected.
`#198` (follow persistence) reuses this same seam to bind the follow repository into
the same transaction as notification creation.

A notification is never persisted without an attempt to queue its deliveries: the unit
of work rolls back the notification insert if enqueueing fails. Conversely, the enqueue
is always attempted even when notification creation was itself a deduplicated no-op
(`created=False`), because the outbound message's own unique
`(notification_id, channel)` constraint plus `ON CONFLICT DO NOTHING` makes a duplicate
enqueue a harmless no-op — so a notification that is somehow missing its message
self-heals on the next call.

See [Outbound Email Delivery](outbound-email-delivery.md) for the full outbox design:
persistence model, claim protocol, retry/backoff, and the delivery worker.

## Typed Domain Extension Pattern

Adding a notification domain requires all of the following:

1. Add the identifier to `NotificationType` and update the PostgreSQL check constraint in a new Alembic migration. The migration test inserts every `NotificationType` member against the migrated schema, so a new enum value fails until its migration exists — repository tests alone will not catch this, because they build the table from the model via `Base.metadata.create_all`.
2. If the notification references a resource, create a domain-owned context table with real foreign keys. Do not add metadata, `resource_type`, or `resource_id` to `notifications`.
3. Add a strict response subtype whose discriminator is the enum member and whose resource fields are typed.
4. Load any required domain context in the repository or service in batches, then map notifications to strict response schemas in `NotificationService` using explicit private helpers.
5. Compute `availableActions` from the authoritative domain state and authorization using `NotificationAction` members. Read state must not influence actionability.
6. Add migration, repository, schema, API-contract, authorization, query-count, frontend, and documentation coverage.

Context loading must tolerate soft-deleted or resolved resources so notifications remain activity history. Text-only types may use only the common table but still need enum, service mapping, frontend, and contract coverage.

The project currently follows its established service-level ORM-to-response mapping convention. A broader review and modernization of response mapping is tracked in [#204](https://github.com/benincasantonio/cinelog_server/issues/204).

## See Also

- [Functional: In-App Notifications](../functional/notifications.md)
- [Outbound Email Delivery](outbound-email-delivery.md) — the durable outbox, claim protocol, and delivery worker
- [Pydantic Types and Validators](pydantic_types_and_validators.md)
- [PostgreSQL Migration](postgres-migration.md)
