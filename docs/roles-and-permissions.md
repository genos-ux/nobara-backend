# Roles & Permissions

Covers listing roles, creating custom roles, assigning permissions, and deleting roles.

---

## Permissions Required

| Action | Permission |
|--------|------------|
| Read roles and permissions | `roles:read` |
| Create or update roles | `roles:write` |
| Delete roles | `roles:delete` |

---

## Available Permissions

The full set of permissions in the system:

| Permission | Controls |
|------------|----------|
| `users:read` | View user list and profiles |
| `users:write` | Update, deactivate, activate users |
| `users:delete` | Delete users |
| `invitations:write` | Send and resend invitations |
| `roles:read` | View roles and permissions |
| `roles:write` | Create and update roles |
| `roles:delete` | Delete roles |
| `posts:read` | View posts |
| `posts:write` | Create and edit posts |
| `posts:delete` | Delete posts |
| `posts:review` | Publish, unpublish, request changes |
| `crm:read` | View CRM records |
| `crm:write` | Create and edit CRM records |
| `crm:delete` | Delete CRM records |
| `admin:access` | Access the SQLAdmin dashboard |

---

## List All Permissions

```
GET /v1/roles/permissions
```

Returns every permission defined in the system. Use this to populate a permissions picker when creating or editing a role.

**Response:**
```json
[
  { "id": "uuid", "name": "posts:read" },
  { "id": "uuid", "name": "posts:write" },
  ...
]
```

---

## List Roles

```
GET /v1/roles
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "admin",
    "description": "Full system access",
    "is_system": true,
    "permissions": [
      { "id": "uuid", "name": "users:read" },
      { "id": "uuid", "name": "posts:review" }
    ]
  },
  {
    "id": "uuid",
    "name": "contributor",
    "description": "Can create and edit posts",
    "is_system": true,
    "permissions": [
      { "id": "uuid", "name": "posts:read" },
      { "id": "uuid", "name": "posts:write" }
    ]
  }
]
```

`is_system: true` roles are seeded by the application and cannot be deleted.

---

## Create Role

```
POST /v1/roles
```

**Request body:**
```json
{
  "name": "editor",
  "description": "Reviews and publishes posts",
  "permission_names": ["posts:read", "posts:review", "posts:write"]
}
```

**Response (201):** The created role object including its permissions.

---

## Update Role

```
PUT /v1/roles/{role_id}
```

Replaces all fields and the full permission set.

**Request body:**
```json
{
  "name": "editor",
  "description": "Updated description",
  "permission_names": ["posts:read", "posts:review"]
}
```

**Response:** Updated role object.

**Side effect:** Every active user currently assigned this role receives a `role_updated` notification.

---

## Delete Role

```
DELETE /v1/roles/{role_id}
```

Returns `204 No Content`. Fails with `400` if the role is a system role (`is_system: true`).

---

## Notes

- When assigning a user to a role (via `PATCH /v1/users/{id}`), use the role's `id` (UUID), not its name.
- A user's effective permissions are derived entirely from their assigned role. There are no per-user overrides.
- Use `GET /v1/auth/me` to get the current user's permission list at runtime.
