# Outbound Email Delivery

A durable transactional outbox plus a dedicated worker process deliver every outbound
email — notification emails and the registration-verification, existing-account, and
password-reset emails that used to be sent inline from `AuthService`. Delivery is
at-least-once, retried with exponential backoff, and survives worker crashes and
restarts without losing a message.

**Scope note:** the table is a generic `outbound_messages` outbox (kind-typed,
channel-generic), not a notification-only `notification_deliveries` table. Every
registered `OutboundMessageKind` — `notification`, `registration_verification`,
`registration_existing_account`, and `password_reset` — flows through the same
persistence, claim, and retry machinery.

## Why a durable outbox

Before this design, `EmailService` was called inline from `AuthService` inside the
request, blocked the event loop with synchronous `smtplib`, had no timeout, and
swallowed every SMTP failure — a failed registration or reset email was simply lost
with the caller told it succeeded. The outbox makes delivery a separate, retried,
observable concern: the API request enqueues a row and returns; a dedicated worker
process delivers it.

## Persistence Model

Alembic revision `007_create_outbound_messages` creates `outbound_messages`. The
revision id is deliberately shorter than the migration's stated purpose would suggest:
Alembic's default `alembic_version.version_num` column is `VARCHAR(32)`, and
`007_create_outbound_messages_table` (34 characters) does not fit — it silently
truncates and the next migration fails with `StringDataRightTruncationError`.

| Column | Purpose |
|---|---|
| `kind` | Closed `OutboundMessageKind`: `notification`, `registration_verification`, `registration_existing_account`, `password_reset` |
| `notification_id` | FK to `notifications.id` ON DELETE CASCADE; required if and only if `kind = 'notification'` |
| `channel` | Closed `OutboundMessageChannel`: `email` only, for now |
| `destination` | Delivery address, snapshotted at enqueue time |
| `subject`, `text_body`, `html_body` | Rendered at enqueue; bodies are cleared once the row reaches a terminal status |
| `status` | Closed `OutboundMessageStatus`: `pending`, `processing`, `delivered`, `failed` |
| `attempt_count` | Incremented at **claim** time, not send time |
| `available_at` | Claimable once `now() >= available_at`; also the retry backoff clock |
| `locked_at` | Set when claimed, cleared on settle; drives stale-lock recovery |
| `delivered_at` | Set on successful delivery |
| `last_error` | Sanitized, truncated failure detail (≤ 500 characters, CHECK-enforced) |

### Constraints and indexes

- `ck_outbound_messages_kind`, `ck_outbound_messages_channel`, `ck_outbound_messages_status` — closed enums
- `ck_outbound_messages_notification_reference` — `(kind = 'notification') = (notification_id IS NOT NULL)`
- `ck_outbound_messages_attempt_count` — `attempt_count >= 0`
- `ck_outbound_messages_last_error_length` — `last_error IS NULL OR char_length(last_error) <= 500`
- `uq_outbound_messages_notification_channel` — **total** (not partial) unique `(notification_id, channel)`. PostgreSQL treats `NULL` as distinct from `NULL`, so auth-kind rows (`notification_id IS NULL`) never collide and can repeat freely. Being total rather than partial means soft-deleting a queued message is a permanent cancel, never a resend.
- `ix_outbound_messages_claimable` — `(channel, available_at, id) WHERE deleted IS FALSE AND status = 'pending'`
- `ix_outbound_messages_stale_locks` — `(locked_at) WHERE deleted IS FALSE AND status = 'processing'`

### Why content is rendered and stored at enqueue

Content cannot be reconstructed later. A registration or password-reset code exists
only as an HMAC hash in Redis once issued
(`app/services/registration_verification_service.py`) — the plaintext code has to be
captured into the rendered body before the message is queued. Rendering therefore
happens once, at enqueue time, and the result is persisted on the row.

### Why bodies are cleared on terminal status

`text_body`/`html_body` are set to `NULL` on `delivered` and on terminal `failed`.
This keeps one-time codes out of long-lived storage. `subject` and `last_error` remain
for audit. A row that is retried (non-terminal `failed`, i.e. scheduled for another
attempt) keeps its bodies, since the message still has to be sent.

## State Machine

```text
pending -> processing -> delivered
                       -> pending (retry, backoff applied)
                       -> failed  (attempts exhausted)
```

## Claim Protocol

`OutboundMessageRepository.claim_pending_messages(channel, *, batch_size)` runs one
transaction:

1. `SELECT ... FOR UPDATE SKIP LOCKED` over claimable rows (`channel`, `status = 'pending'`,
   `available_at <= now()`, active), ordered by `(available_at, id)`, limited to
   `batch_size`.
2. `UPDATE ... WHERE id IN (...)` setting `status = 'processing'`, `locked_at = now()`,
   `attempt_count = attempt_count + 1`.
3. Commit.

Row locks acquired by step 1 are held until the commit in step 3, so a second worker's
`SKIP LOCKED` select passes over them — this is what makes concurrent workers safe
without any external coordination.

**Attempt count increments at claim time**, before delivery is attempted. A worker that
crashes mid-send still burns an attempt, so a poison message cannot loop forever even
across worker restarts.

## At-Least-Once Delivery

`OutboundMessageDeliveryService._deliver()` sends first, then calls `mark_delivered()`
only after a successful send. There is no guard requiring `status = 'processing'` on
`mark_delivered()`: if a stale-lock sweep (see below) already requeued the row
concurrently, the mail was still sent, and recording delivery here is exactly what
prevents a duplicate send on the next claim. The accepted trade-off is a rare
duplicate delivery, never a lost one.

Sending itself runs off the event loop
(`await asyncio.to_thread(email_service.send_transactional_email, ...)`), since
`smtplib` is blocking. No `aiosmtplib` dependency was added for this.

## Retry and Backoff

On failure, `_record_failure()`:

- If `attempt_count >= max_attempts`: `mark_failed()` — terminal, bodies cleared.
- Otherwise: `schedule_retry(delay=compute_retry_delay(attempt_count, config))` — bodies
  retained, `available_at = now() + delay` (bound as a PostgreSQL `INTERVAL`, so the
  retry clock is owned by the database, not the worker's local clock).

`compute_retry_delay()` (`app/config/outbound_message_config.py`) doubles per attempt
with no jitter, capped at `retry_max_delay`:

| Attempt that just failed | Delay before next attempt (defaults) |
|---|---|
| 1 | 60s |
| 2 | 120s |
| 3 | 240s |
| 4 | 480s |
| 5 (exhausted at default `max_attempts=5`) | terminal `failed` |

Every failure detail is passed through `sanitize_failure_detail()`
(`app/utils/sanitize_utils.py`) before being persisted: whitespace is collapsed, email
addresses and `password=`/`auth:`-style fragments are redacted, and the result is
truncated to `MAX_FAILURE_DETAIL_LENGTH` (500 characters). The database CHECK
constraint on `last_error` is the enforced backstop regardless.

## Stale-Lock Recovery

A worker that crashes or is killed mid-batch leaves rows `processing` with a stale
`locked_at`. `OutboundMessageRepository.recover_stale_locks(lock_timeout, max_attempts)`
runs once per delivery cycle (`OutboundMessageDeliveryService.run_once()` calls it
before claiming), in one transaction, two `UPDATE`s over
`status = 'processing' AND active() AND locked_at < now() - lock_timeout`:

1. Rows with `attempt_count >= max_attempts` are marked `failed` (exhausted rule — a
   crash-orphaned row does not get a free extra attempt beyond the configured limit).
2. The remaining stale rows are requeued to `pending` with `available_at = now()`.

The two updates share the same stale-lock predicate but disjoint attempt-count ranges,
so a row can only match one of them, and a row with a fresh lock (still within
`lock_timeout`) is left untouched by either.

## Renderer Registry

`app/services/outbound_email_renderer.py` is a pure module: no I/O, no repository
dependency.

- **Notification emails** are rendered from a registry keyed by `NotificationType`
  (`_NOTIFICATION_RENDERERS`), with every member registered explicitly. A contract test
  asserts `set(_NOTIFICATION_RENDERERS) == set(NotificationType)`, so a new
  notification type without a registered renderer fails that test rather than silently
  going unsent. The shared renderer (`_render_persisted_text`) uses the persisted
  `title` as the subject and the persisted `body` as the email content verbatim in the
  plaintext body — this makes "email content matches the in-app text" mechanically
  true, with no separate locale or copy to maintain. Because `title`/`body` embed
  user-supplied values (handles, names), they are passed through `html.escape()` before
  being embedded in the HTML body.
- An unregistered notification type makes `render_notification_email()` return `None`,
  and `OutboundMessageService.enqueue_notification_email()` raises rather than queueing
  a row that could never be sent. The registry contract test keeps this path
  unreachable in practice.
- **Auth renderers** (`render_registration_verification`,
  `render_registration_existing_account`, `render_password_reset`) reproduce the exact
  subjects and copy that used to live directly in `EmailService` — moved verbatim so
  the wire content did not change when delivery became asynchronous.
- No deep links or CTA URLs are rendered in this design (that needs a new
  `APP_WEB_BASE_URL` setting) — noted here as a follow-up, not implemented.

## Enqueue Path

`OutboundMessageService` (`app/services/outbound_message_service.py`) is the only
thing that touches rendering. It has no SMTP dependency — only the outbound-message
repository and the user repository (to resolve a notification recipient's email
address, which is looked up and snapshotted onto the row at enqueue time; a later
email change on the account does not retroactively redirect an already-queued
message).

- `enqueue_notification_email(notification, *, session=None)` — used by
  `NotificationUnitOfWork`.
- `enqueue_registration_verification(email, code)`,
  `enqueue_registration_existing_account(email)`,
  `enqueue_password_reset(email, code)` — used by `AuthService`.

### Notification creation is one transaction

`NotificationUnitOfWork.create_notification_with_deliveries()`
(`app/repository/notification_unit_of_work.py`) opens one session, creates the
notification via `NotificationRepository.create_notification(data, session=session)`,
enqueues one outbound message per requested channel via
`OutboundMessageService.enqueue_notification_email(notification, session=session)`, and
commits — or rolls back the whole thing on any exception. This is the transaction seam
introduced by `RepositoryBase._unit_of_work()`; see the "Repository Conventions" bullet
in [ARCHITECTURE.md](../../ARCHITECTURE.md). **The enqueue is always attempted, even
when the notification already existed** (`created is False` on a deduplicated create):
the unique `(notification_id, channel)` constraint plus `ON CONFLICT DO NOTHING` makes
the duplicate enqueue a database-level no-op, so a notification that is somehow missing
its message self-heals on the next call. `#198` (follow persistence) extends this class
to bind the follow repository into the same unit of work.

### Auth emails moved onto the outbox

`AuthService` no longer holds an `EmailService`. `send_registration_verification_code()`,
`register()`'s existing-account branch, and `forgot_password()` now call
`OutboundMessageService.enqueue_*()` instead of sending inline. The API responses,
status codes, rate limits, and enumeration-safety behavior are unchanged — only the
send itself moved out of the request/response cycle and became durable. The enqueue for
`forgot_password()` is a separate transaction from `set_reset_password_code()`; if the
enqueue fails, the request errors and the client can retry, which is strictly better
than the previous silent loss.

## EmailService: Transport Only

`EmailService` (`app/services/email_service.py`) no longer knows about registration
codes or reset copy — it is pure transport.

- `is_configured()` — `True` when `EMAIL_TRANSPORT == "console"`, or when
  `SMTP_SERVER` is set. Drives the worker's fail-fast startup check.
- `send_transactional_email(*, to_email, subject, text, html)` — the only public send
  API. The console transport prints instead of sending and never raises. The SMTP
  transport raises `EmailDeliveryError` when unconfigured or when the underlying send
  fails (`smtplib.SMTPException` / `OSError`), wrapping the original exception.
- SSL is used for port 465 or when `SMTP_USE_SSL=true`; `SMTP_TIMEOUT_SECONDS` is
  passed to `smtplib.SMTP`/`SMTP_SSL` and must stay well below
  `OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS` — a send that hangs past the lock timeout
  would let a stale-lock sweep requeue a message that is still in flight.

## Environment Variables

| Env var | Default | Purpose |
|---|---|---|
| `OUTBOUND_MESSAGE_BATCH_SIZE` | `10` | Rows claimed per delivery cycle |
| `OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS` | `5` | Worker sleep after an empty cycle |
| `OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS` | `300` | Age at which a `processing` lock is considered stale |
| `OUTBOUND_MESSAGE_MAX_ATTEMPTS` | `5` | Attempts before a message is terminally `failed` |
| `OUTBOUND_MESSAGE_RETRY_BASE_SECONDS` | `60` | First retry backoff |
| `OUTBOUND_MESSAGE_RETRY_MAX_SECONDS` | `3600` | Backoff cap |
| `EMAIL_TRANSPORT` | `smtp` | `smtp` or `console` |
| `SMTP_TIMEOUT_SECONDS` | `10` | Socket timeout for SMTP sends |
| `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_SSL` | — | Standard SMTP transport settings |

`EMAIL_TRANSPORT=console` replaces the old implicit "SMTP unset → print a mock"
behavior with an explicit opt-in: local dev without Mailpit still sees codes (now in
the worker's stdout), while a misconfigured production worker refuses to start instead
of silently discarding mail.

## Running Locally

```bash
make run-email-worker     # uv run python -m app.workers.outbound_message_worker
```

Or via the full local Docker stack (`make docker-up`), which starts `postgres` →
`db-migrate` → `api` + `email-worker` + `mailpit`. Mailpit's web UI is at
`http://localhost:8025`; the local `email-worker` service points `SMTP_SERVER=mailpit`.

## Runbook

- **Inspect failed rows**:
  `SELECT id, kind, destination, attempt_count, last_error, updated_at FROM outbound_messages WHERE status = 'failed' ORDER BY updated_at DESC;`
- **Cancel a queued message**: soft-delete it (`UPDATE outbound_messages SET deleted = TRUE WHERE id = ...`).
  The claim query filters on `deleted IS FALSE`, so a soft-deleted row is never picked
  up again. Because the notification/channel uniqueness constraint is total (not
  partial), this is a permanent cancel — the row cannot be recreated for that
  notification/channel pair.
- **Force a retry sooner**: `UPDATE outbound_messages SET available_at = now() WHERE id = ...`
  (only meaningful while `status = 'pending'`).

## See Also

- [ARCHITECTURE.md](../../ARCHITECTURE.md) — `OutboundMessage` data model, Background Workers, Repository Conventions
- [Notification Architecture](notifications.md) — the notification side of the unit of work
- [Functional: In-App Notifications](../functional/notifications.md) — user-facing email notification behavior
- [Technical: Authentication](authentication.md) — registration/reset email queuing
