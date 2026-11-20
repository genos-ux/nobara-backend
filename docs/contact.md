# Contact Form

Public visitors (people who have not signed up) can submit a contact form. The
backend saves the submission to the database — **no email is sent**.

Submissions are stored in the existing CRM tables:

- A `Person` is created (or reused) by email address.
- An `Activity` is created with `activity_type = "contact_form"`, the visitor's
  subject, and the message as the description.

When a person already exists, their name is only filled in if it is currently
missing; a name set by staff is never overwritten. The CRM `stage` is left
untouched, so an existing client stays a client.

---

## Permissions Required

| Action | Permission |
|--------|------------|
| Submit the form (public) | None |
| List submissions | `crm:read` |

The `admin` and `contributor` roles have `crm:read` by default.

---

## Submit a Contact Message

```
POST /v1/contact-messages
```

Public — no `Authorization` header is required.

### Request

```json
{
  "name": "Jane Visitor",
  "email": "jane@example.com",
  "subject": "Question about plans",
  "message": "I would like to know more about your services."
}
```

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | 1–255 characters, not blank |
| `email` | string | Valid email address |
| `subject` | string | 1–255 characters, not blank |
| `message` | string | 1–5000 characters, not blank |

### Response `201 Created`

```json
{
  "id": "activity-uuid",
  "person_id": "person-uuid",
  "name": "Jane Visitor",
  "email": "jane@example.com",
  "subject": "Question about plans",
  "message": "I would like to know more about your services.",
  "created_at": "2026-11-20T12:00:00Z"
}
```

---

## List Customers & Messages

```
GET /v1/contact-messages?page=1&page_size=20
```

Requires `Authorization: Bearer <access_token>` with `crm:read`.

| Param | Type | Description |
|-------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page, 1–100 (default: 20) |

### Response `200 OK`

Each item contains the customer's `name`, `email`, and `message`.

```json
{
  "items": [
    {
      "name": "Jane Visitor",
      "email": "jane@example.com",
      "message": "I would like to know more about your services."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

Newest submissions are returned first. The same customer may appear more than
once if they submitted the form multiple times.

---

## Admin Dashboard

Contact submissions also appear in the SQLAdmin dashboard under **CRM →
Activities**. Filter on `activity_type = "contact_form"` to see only form
submissions. The person's name and email are visible via the linked `Person`.

---

## Notes

- Each submission creates a new activity, even when the same email was used
  before. Repeat contacts remain visible in the person's activity history.
- There is no built-in rate limiting or captcha yet. Add spam protection at the
  frontend or as middleware if abuse appears.
- Every submission writes a `contact.received` audit log entry with the
  visitor's email as `actor_email` and no `actor_id`.
