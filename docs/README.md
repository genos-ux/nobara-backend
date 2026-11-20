# Nabora CRM — Frontend Integration Guides

This folder contains feature-by-feature integration guides for frontend developers building against the Nabora CRM API.

## Contents

| Guide | Description |
|-------|-------------|
| [Authentication](./authentication.md) | Login, logout, token refresh, password change/reset, user profile |
| [Users & Invitations](./users-and-invitations.md) | User management, inviting new users, accepting invitations |
| [Roles & Permissions](./roles-and-permissions.md) | RBAC — listing, creating, updating, and deleting roles |
| [Contact Form](./contact.md) | Public contact form submissions saved to the CRM |
| [Posts](./posts.md) | Post lifecycle: drafts, review workflow, publish/unpublish |
| [Notifications](./notifications.md) | REST endpoints and real-time SSE stream |

## Base URL & Auth

All endpoints are prefixed with `/v1`. Every authenticated request requires:

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

Unauthenticated endpoints (login, invitation accept, forgot/reset password) need no `Authorization` header.

## Error Codes

| Status | Meaning |
|--------|---------|
| 400 | Bad request / business rule violation |
| 401 | Missing, invalid, or expired token — refresh or redirect to login |
| 403 | Authenticated but missing the required permission |
| 404 | Resource not found |
| 409 | Conflict (e.g. duplicate email) |
| 422 | Missing or malformed request fields |

A `401` on a protected endpoint means no usable access token was sent. A `403` means the token is valid but the user lacks the required permission.

## Interactive API Docs

When the server is running you can explore every endpoint at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
