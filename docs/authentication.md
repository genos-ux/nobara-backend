# Authentication

Covers login, token management, profile, password change, and logout.

---

## Login

```
POST /v1/auth/login
```

No authentication required.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

**Response:**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>"
}
```

Store both tokens. The access token expires after 30 minutes. The refresh token lasts 7 days.

**Side effect:** If this is the user's first login (no prior notifications), a `welcome` notification is created for them.

---

## Get Current User Profile

```
GET /v1/auth/me
```

**Response:**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "role": "contributor",
  "permissions": ["posts:read", "posts:write"],
  "is_active": true,
  "is_email_pending": false
}
```

Call this once after login and cache it. The `permissions` array drives which UI features you show or hide. Re-fetch it after a role change.

`is_email_pending: true` means an admin updated the user's email address but it has not yet been confirmed.

---

## Refresh Access Token

```
POST /v1/auth/refresh
```

No `Authorization` header needed — pass the refresh token in the body.

**Request body:**
```json
{
  "refresh_token": "<jwt>"
}
```

**Response:** Same shape as login — a new `access_token` and `refresh_token`.

**When to call:** Intercept any `401` response, attempt a refresh, then retry the original request. If the refresh also returns `401`, the session has fully expired — redirect to login.

---

## Change Password

```
POST /v1/auth/change-password
```

**Request body:**
```json
{
  "current_password": "oldPassword",
  "new_password": "newPassword123"
}
```

Validation rules:
- `new_password` must be at least 8 characters.
- `new_password` must differ from `current_password`.

**Response:**
```json
{ "message": "Password updated successfully" }
```

**Side effect:** Creates a `password_changed` notification for the user.

---

## Logout

```
POST /v1/auth/logout
```

The server is stateless — there is no token blocklist. On success, discard both tokens from client storage and redirect to the login page.

**Response:**
```json
{ "message": "Successfully logged out" }
```

---

## Token Storage Recommendation

Store tokens in memory or `httpOnly` cookies. Avoid `localStorage` in security-sensitive contexts. Always use HTTPS in production.

---

## Suggested Auth Flow

```
1.  User submits login form
2.  POST /v1/auth/login → store access_token + refresh_token
3.  GET  /v1/auth/me    → cache user profile + permissions
4.  On every API request → attach Authorization: Bearer <access_token>
5.  On 401 response     → POST /v1/auth/refresh
      Success           → update stored tokens, retry request
      Failure           → clear tokens, redirect to login
6.  On logout           → POST /v1/auth/logout, clear tokens, redirect
```
