# Notifications

Covers REST endpoints for reading and managing notifications, plus the real-time SSE stream.

No special permission is required — every authenticated user can access their own notifications.

---

## Notification Object Shape

```json
{
  "id": "uuid",
  "type": "post_published",
  "title": "Post published",
  "message": "Your post 'Why protein matters' has been published.",
  "post_id": "uuid",
  "is_read": false,
  "created_at": "2026-11-16T08:00:00Z",
  "read_at": null
}
```

`post_id` is set for post-related notifications and `null` for all others. Use it to link directly to the relevant post.

---

## Notification Types

| Type | Triggered by |
|------|-------------|
| `welcome` | First login |
| `account_created` | Account created via invitation |
| `user_updated` | Admin updates the user's details |
| `user_deactivated` | Admin deactivates the account |
| `user_activated` | Admin reactivates the account |
| `password_changed` | User changes their password |
| `role_changed` | User's role is changed |
| `role_updated` | A role the user holds was edited by an admin |
| `invitation_accepted` | An invited user accepts their invitation |
| `post_submitted` | A post is submitted for review (sent to reviewers) |
| `post_published` | A post the user authored is published |
| `post_unpublished` | A post the user authored is unpublished |
| `post_changes_requested` | Reviewer requests changes on the user's post |
| `post_updated` | A post is edited |
| `post_deleted` | A post is deleted |

---

## REST Endpoints

### List Notifications

```
GET /v1/notifications
```

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page, 1–100 (default: 20) |
| `unread_only` | boolean | Only return unread notifications (default: false) |

**Response:**
```json
{
  "items": [ ...notification objects... ],
  "total": 12,
  "page": 1,
  "page_size": 20,
  "pages": 1,
  "unread_count": 3
}
```

`unread_count` is always the total unread count, regardless of the `unread_only` filter. Use it to update the notification badge without a separate request.

Results are ordered newest first.

---

### Unread Count

```
GET /v1/notifications/unread-count
```

**Response:**
```json
{ "count": 3 }
```

Use this to power a badge on the notification bell icon.

---

### Mark All Read

```
POST /v1/notifications/read-all
```

No body required. Marks every unread notification for the current user as read.

**Response:**
```json
{ "updated": 3 }
```

---

### Mark One Notification Read

```
PATCH /v1/notifications/{notification_id}/read
```

**Response:** The updated notification object with `is_read: true` and `read_at` populated.

Returns `404` if the notification doesn't exist or belongs to a different user.

This call is idempotent — marking an already-read notification read returns `200` with no error.

---

## Real-Time Notifications via SSE

The SSE stream pushes new notifications to the client as they happen, without polling.

`EventSource` cannot send an `Authorization` header, so authentication uses a short-lived ticket instead of the standard Bearer token.

### Step 1 — Exchange Bearer Token for a Ticket

```
POST /v1/notifications/stream-ticket
```

Requires `Authorization: Bearer <access_token>`.

**Response:**
```json
{
  "ticket": "<short-lived jwt>",
  "expires_in_seconds": 60
}
```

The ticket is valid for 60 seconds. Request a fresh one before opening the stream — do not cache it.

---

### Step 2 — Open the SSE Stream

```
GET /v1/notifications/stream?ticket=<ticket>
```

No `Authorization` header needed. The ticket in the query string authenticates the connection.

**Response headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

---

### Events

#### `connected`

Sent immediately on stream open.

```
event: connected
data: {"unread_count": 3}
```

Use `unread_count` to initialise the notification badge.

#### `notification`

Sent whenever a new notification is created for the user.

```
id: <notification-uuid>
event: notification
data: { ...full notification object... }
```

Each event carries an `id` field — the notification's UUID. Store the last received `id` to support reconnection.

#### Keep-alive

Sent every ~20 seconds when no notification has been delivered. This keeps the connection alive through proxies.

```
: keep-alive
```

---

### Reconnection with `Last-Event-ID`

If the connection drops, open a new stream and pass the last notification `id` you received in the `Last-Event-ID` header. The server will replay any notifications you missed.

```
GET /v1/notifications/stream?ticket=<fresh-ticket>
Last-Event-ID: <last-notification-uuid>
```

`EventSource` sends `Last-Event-ID` automatically when you use the `id:` field in SSE events.

---

### Full Browser Example

```js
async function openNotificationStream(accessToken) {
  // 1. Exchange Bearer token for a short-lived ticket
  const { ticket } = await fetch('/v1/notifications/stream-ticket', {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
  }).then(r => r.json())

  // 2. Open the SSE stream (EventSource handles reconnection automatically)
  const es = new EventSource(`/v1/notifications/stream?ticket=${ticket}`)

  es.addEventListener('connected', (e) => {
    const { unread_count } = JSON.parse(e.data)
    updateBadge(unread_count)
  })

  es.addEventListener('notification', (e) => {
    const notification = JSON.parse(e.data)
    showToast(notification.title, notification.message)
    incrementBadge()
  })

  es.onerror = () => {
    // EventSource reconnects automatically, but the ticket will be expired.
    // On reconnect, fetch a new ticket and re-open the stream.
    es.close()
    openNotificationStream(accessToken)
  }

  return es
}
```

> **Note on tickets and reconnection:** `EventSource` retries automatically on network drops, but the query-string ticket will be expired after 60 seconds. The `onerror` handler above closes the stale connection and opens a fresh one with a new ticket. In practice, fetch a new ticket inside `onerror` before reopening.

---

## Polling Alternative

If SSE is not suitable for your environment, poll `GET /v1/notifications/unread-count` on an interval (e.g. every 30 seconds) and fetch the full list when the count increases.
