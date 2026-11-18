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

## Forgot Password

```
POST /v1/auth/forgot-password
```

No authentication required.

**Request body:**
```json
{
  "email": "user@example.com"
}
```

**Response (always the same, whether or not the account exists):**
```json
{
  "message": "If an account with that email exists, a password reset link has been sent."
}
```

If the email belongs to an active account, a reset link is emailed to that address. The link points to:

```
{FRONTEND_URL}/dashboard/forgot-password?token=<jwt>
```

The token expires after `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (default 30 minutes). Requesting another reset invalidates the previous link. Pending invited users who have not set a password are ignored — they should use their invitation link.

**Side effect:** Creates an `auth.password_reset_requested` audit log entry.

---

## Reset Password

```
POST /v1/auth/reset-password
```

No authentication required — the reset token proves ownership of the email address.

**Request body:**
```json
{
  "token": "<token from the reset email>",
  "new_password": "newPassword123"
}
```

Validation rules:
- `new_password` must be at least 8 characters.
- `new_password` must differ from the current password.

**Response:**
```json
{ "message": "Password reset successfully" }
```

The token is single-use. A successful reset invalidates the link and creates a `password_changed` notification for the user. Log in again with the new password afterwards.

**Errors:** an invalid, expired, or already-used token returns `401`.

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
