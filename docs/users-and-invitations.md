# Users & Invitations

Covers listing and managing users, inviting new members, and the invitation accept flow.

---

## Permissions Required

| Action | Permission |
|--------|------------|
| Read users | `users:read` |
| Update / deactivate / activate users | `users:write` |
| Send or resend invitations | `invitations:write` |
| Accept invitation | None — public endpoint |

---

## Users

### List Users

```
GET /v1/users
```

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page, 1–100 (default: 10) |
| `search` | string | Filter by name or email (optional) |
| `role_id` | UUID | Filter by role (optional) |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "full_name": "Jane Doe",
      "email": "jane@example.com",
      "role": "contributor",
      "is_active": true,
      "is_pending": false,
      "is_email_pending": false,
      "post_count": 3,
      "posts": [
        {
          "id": "uuid",
          "headline": "Why protein matters",
          "topic": "Nutrition Basics",
          "section": "nutrition",
          "status": "published",
          "updated_at": "2026-11-15T10:00:00Z"
        }
      ]
    }
  ],
  "total": 24,
  "page": 1,
  "page_size": 10,
  "pages": 3
}
```

**Status flags:**
- `is_pending: true` — invited but hasn't set their password yet.
- `is_email_pending: true` — email was updated by an admin but not yet confirmed.

---

### Get Single User

```
GET /v1/users/{user_id}
```

**Response:**
```json
{
  "id": "uuid",
  "full_name": "Jane Doe",
  "email": "jane@example.com",
  "role": "contributor",
  "is_active": true,
  "is_email_pending": false
}
```

---

### Update User

```
PATCH /v1/users/{user_id}
```

At least one field is required.

**Request body:**
```json
{
  "full_name": "Jane Smith",
  "email": "jane.smith@example.com",
  "role_id": "uuid"
}
```

**Response:** Updated user object (same shape as Get Single User).

**Side effects:**
- Changing a user's role creates a `role_changed` notification for them.
- Changing the email sets `is_email_pending: true` until confirmed.

---

### Deactivate User

```
PATCH /v1/users/{user_id}/deactivate
```

No body required. The user can no longer log in. Returns the updated user object with `is_active: false`.

**Side effect:** Creates a `user_deactivated` notification for the user.

---

### Activate User

```
PATCH /v1/users/{user_id}/activate
```

No body required. Re-enables a deactivated account. Returns the updated user object with `is_active: true`.

**Side effect:** Creates a `user_activated` notification for the user.

---

## Invitations

### Invite a New User

```
POST /v1/invitations
```

Creates a pending user account and sends them an email with a link to set their password.

**Request body:**
```json
{
  "full_name": "John Smith",
  "email": "john@example.com",
  "role_id": "uuid"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "full_name": "John Smith",
  "email": "john@example.com",
  "role": "contributor",
  "is_pending": true,
  "is_email_pending": false
}
```

The user appears in the user list with `is_pending: true` until they accept.

---

### Resend Invitation

```
POST /v1/invitations/resend
```

Generates a fresh token and re-sends the invitation email. Use this for expired links or when the user never received the first email.

**Request body** — provide `user_id` or `email`, not both:
```json
{ "user_id": "uuid" }
```
or
```json
{ "email": "john@example.com" }
```

**Response:**
```json
{
  "id": "uuid",
  "full_name": "John Smith",
  "email": "john@example.com",
  "role": "contributor",
  "is_pending": true,
  "is_email_pending": false,
  "expires_in_days": 7,
  "message": "Invitation re-sent to john@example.com. The link expires in 7 day(s)."
}
```

---

### Accept Invitation

```
POST /v1/invitations/accept
```

**No authentication required.** The invitation token from the email link acts as proof of identity.

This is what your invitation landing page (e.g. `/invite/accept?token=...`) calls when the user submits their new password.

**Request body:**
```json
{
  "token": "<token from invitation email link>",
  "password": "newPassword123"
}
```

**Response:**
```json
{
  "id": "uuid",
  "full_name": "John Smith",
  "email": "john@example.com",
  "role": "contributor",
  "is_pending": false,
  "is_email_pending": false
}
```

After a successful response, redirect the user to the login page. `is_pending` will now be `false`.

---

## Invitation Flow (End-to-End)

```
Admin:
  1. POST /v1/invitations  →  user created (is_pending: true), email sent

New user (email):
  2. Clicks link: https://yourapp.com/invite/accept?token=<token>

Frontend (invitation page):
  3. User fills in a password
  4. POST /v1/invitations/accept  →  account activated (is_pending: false)
  5. Redirect to /login

If link expired:
  Admin: POST /v1/invitations/resend  →  fresh link sent
```
