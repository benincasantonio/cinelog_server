# In-App Notifications

Cinelog provides an authenticated, persisted notification inbox for activity history. Notification text is rendered in English by the server and returned exactly as stored.

## Notification Shape

Every notification contains common presentation and read-state fields:

```json
{
  "id": "d51b78c5-1847-49dc-826f-461c87974c60",
  "type": "follow.started",
  "title": "New follower",
  "body": "A user started following you.",
  "actor": {
    "handle": "moviefan",
    "firstName": "Movie",
    "lastName": "Fan"
  },
  "availableActions": [],
  "readAt": null,
  "createdAt": "2026-07-18T10:30:00Z"
}
```

`actor` is `null` when an event has no actor or that account has been deleted. `availableActions` is always present. The generic inbox currently returns an empty list; later notification domains may expose registered actions when their underlying workflow still permits them.

## List the Inbox

```http
GET /v1/notifications?unreadOnly=false&limit=20&cursor=...
```

All notification endpoints require authentication. `limit` defaults to 20 and accepts 1–100. Results are newest first. Pass the opaque `nextCursor` value unchanged to request the next page.

The query string is strict: `unreadOnly`, `limit`, and `cursor` are the only accepted parameters, and any other parameter — including cache-busters such as `?_=1699999999` — is rejected with `422`. Cursors are signed and bound to the authenticated user, so a cursor issued to one account is rejected for every other account. A malformed, truncated, or foreign cursor returns `422 INVALID_PAGINATION_CURSOR`; rotating the server's cursor signing secret has the same effect, and clients recover by restarting pagination without a cursor.

```json
{
  "items": [],
  "nextCursor": null,
  "unreadCount": 0
}
```

`unreadCount` is the total active unread count for the authenticated user across all pages. It does not change when `unreadOnly=true`, and it is separate from workflow-specific counts such as pending follow requests.

Listing, filtering, paginating, scrolling, and rendering notifications are read-only operations. They never mark a notification as read.

## Mark One Notification Read

```http
PATCH /v1/notifications/{notification_id}/read
X-CSRF-Token: <token>
```

The request has no body. The server sets `readAt` using its database timestamp and returns the updated notification with HTTP 200. Repeating the request is safe and returns the original persisted timestamp. A missing notification and another user's notification both return `404 NOTIFICATION_NOT_FOUND`.

## Mark All Notifications Read

```http
POST /v1/notifications/read-all
X-CSRF-Token: <token>
```

The server marks the authenticated user's current unread notifications with one timestamp:

```json
{
  "updatedCount": 3,
  "unreadCount": 0
}
```

Already-read rows retain their original timestamp. Repeating the operation returns `updatedCount: 0` unless new unread notifications have arrived. A notification inserted concurrently after the update can remain unread and is reflected in the returned `unreadCount` when visible to the final count query.

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `GET /v1/notifications` | 60 requests per minute |
| `PATCH /v1/notifications/{notification_id}/read` | 60 requests per minute |
| `POST /v1/notifications/read-all` | 10 requests per minute |

Limits are per authenticated user. See [Rate Limiting](rate-limiting.md) for headers and `429` behavior.

## Email Notifications

Every notification also queues an email — the same events that appear in the in-app
inbox are emailed to the recipient's address on file. The email content matches the
in-app notification: the subject is the notification's title and the body is the
notification's body, in English, exactly as stored. There is no separate copy to
translate or keep in sync.

Delivery is asynchronous and at-least-once: creating a notification returns as soon as
the email is durably queued, not once it is actually sent, and a rare duplicate email
is possible (never a lost one) if a delivery attempt succeeds right as the system
recovers from an interruption. The destination address is a snapshot of the
recipient's email at the moment the notification was created — a later email change on
the account does not retroactively redirect an already-queued message.

See [Technical: Outbound Email Delivery](../technical/outbound-email-delivery.md) for
the delivery mechanism.

## Workflow Boundary

Read state is presentation state only. Reading a notification never accepts a follow request or changes another domain resource. The owning domain API remains the source of truth for whether an action is currently available. There is no mark-unread operation.

## See Also

- [Technical: Notification Architecture](../technical/notifications.md)
- [Technical: Outbound Email Delivery](../technical/outbound-email-delivery.md)
