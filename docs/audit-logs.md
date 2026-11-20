# Audit Logs

The audit log records every significant action that happens in the system — who did what, to which resource, and when. It is append-only and immutable from the API; entries are written automatically by the backend on every domain event.

---

## Permission Required

| Action | Permission |
|--------|------------|
| Read audit logs | `audit:read` |

Only the `admin` role has `audit:read` by default. No other role can access this endpoint unless you explicitly grant them the permission.

---

## Endpoint

```
GET /v1/audit-logs
```

Returns a paginated list of audit log entries, newest first.

---

## Query Parameters

All parameters are optional and can be combined freely.

| Param | Type | Description |
|-------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page, 1–200 (default: 50) |
| `actor_id` | UUID | Filter by the user who performed the action |
| `action` | string | Filter by action string (e.g. `post.published`) |
| `resource_type` | string | Filter by resource type (`user`, `post`, `role`) |
| `resource_id` | string | Filter by the specific resource ID |
| `since` | ISO 8601 datetime | Only entries at or after this time |
| `until` | ISO 8601 datetime | Only entries at or before this time |

---

## Response

```json
{
  "items": [
    {
      "id": "uuid",
      "actor_id": "uuid",
      "actor_email": "admin@example.com",
      "action": "post.published",
      "resource_type": "post",
      "resource_id": "uuid",
      "detail": "Post 'Why protein matters' published by 'Admin'.",
      "ip_address": null,
      "created_at": "2026-11-16T12:00:00Z"
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 50,
  "pages": 3
}
```

**Fields:**

- `actor_id` / `actor_email` — the user who triggered the event. Both are `null` for system-initiated entries.
- `action` — dot-namespaced action string (see full list below).
- `resource_type` — the kind of resource affected (`user`, `post`, `role`).
- `resource_id` — the UUID of the affected resource as a string.
- `detail` — a human-readable sentence describing exactly what happened.
- `ip_address` — the client IP, populated when available. Currently `null` in most deployments (can be added via middleware).

---

## Action Reference

### Auth

| Action | Triggered by |
|--------|-------------|
| `auth.login` | Successful login |
| `auth.logout` | Logout request |
| `auth.token_refreshed` | Access token refreshed |
| `auth.password_changed` | User changes their own password |

### Users

| Action | Triggered by |
|--------|-------------|
| `user.created` | New user account created (via invitation) |
| `user.updated` | Admin updates name, email, or role |
| `user.deactivated` | Admin deactivates an account |
| `user.activated` | Admin reactivates an account |

### Invitations

| Action | Triggered by |
|--------|-------------|
| `invitation.sent` | Admin invites a new user |
| `invitation.resent` | Admin re-sends an invitation |
| `invitation.accepted` | Invited user sets their password |

### Roles

| Action | Triggered by |
|--------|-------------|
| `role.created` | Admin creates a new role |
| `role.updated` | Admin updates a role's name, description, or permissions |
| `role.deleted` | Admin deletes a role |

### Posts

| Action | Triggered by |
|--------|-------------|
| `post.created` | Author creates a post |
| `post.updated` | Author or admin edits a post |
| `post.deleted` | Author or admin deletes a post |
| `post.submitted` | Author submits a post for review |
| `post.published` | Admin/reviewer publishes a post |
| `post.unpublished` | Admin/reviewer unpublishes a post |
| `post.changes_requested` | Admin/reviewer requests changes on a post |

### Contact Form

| Action | Triggered by |
|--------|-------------|
| `contact.received` | A visitor submits the public contact form |

Contact submissions have no `actor_id`; the visitor's email is stored in
`actor_email` and the created CRM person is the `resource_id`.

---

## Example Queries

**All logins in the last 24 hours:**
```
GET /v1/audit-logs?action=auth.login&since=2026-11-15T12:00:00Z
```

**Everything a specific user did:**
```
GET /v1/audit-logs?actor_id=<user-uuid>
```

**All changes to a specific post:**
```
GET /v1/audit-logs?resource_type=post&resource_id=<post-uuid>
```

**All role management events:**
```
GET /v1/audit-logs?resource_type=role
```

**All activity within a time window:**
```
GET /v1/audit-logs?since=2026-11-16T00:00:00Z&until=2026-11-16T23:59:59Z
```

---

## Design Notes

- **Append-only.** There is no API to update or delete audit log entries. Entries are only written by the backend.
- **Best-effort.** Audit writes happen after the main transaction commits. If an audit write fails, the original action is not rolled back — the failure is logged at the server level.
- **Actor is preserved.** `actor_email` is stored at write time, so renaming or deleting a user does not erase their history from the log. `actor_id` is set to `null` via a `SET NULL` foreign key when a user is deleted, but `actor_email` remains.
- **No PII scrubbing.** Email addresses appear in the log. If you need to comply with a right-to-erasure request, manually nullify `actor_email` in the database for the relevant entries after deleting the user.
