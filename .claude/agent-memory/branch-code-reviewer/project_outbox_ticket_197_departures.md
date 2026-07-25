---
name: outbox-ticket-197-departures
description: Two departures from GitHub issue #197's original text were pre-agreed with the developer; the issue body was later edited to match what was built
metadata:
  type: project
---

Issue #197 ("durable email delivery outbox and worker") was implemented with two
deliberate departures from its original text, both agreed with the developer *before*
implementation:

1. The table is a generic, kind-typed `outbound_messages` outbox rather than a
   notification-scoped `notification_deliveries`. Registration-verification,
   existing-account, and password-reset emails were migrated onto it as well, so
   "existing registration/password-reset behavior remains compatible" was redefined to
   mean identical content and API responses, with delivery moving from inline to
   queued/asynchronous.
2. Delivery logic lives in `app/services/` (`OutboundMessageDeliveryService`);
   `app/workers/` holds only process concerns (signal handling, poll loop, logging).

**Why:** the developer wanted one outbox rather than a notification-only table, and
wanted the delivery cycle unit-testable without `asyncio.run`/signal handling.

**How to apply:** the GitHub issue body for #197 was edited after the fact to describe
what was built, so it is no longer the specification. When judging this work — or
follow-ups like #198 (follow persistence, which extends `NotificationUnitOfWork`) —
do not flag these two choices as deviations. The original acceptance criteria still
apply on every other point.
