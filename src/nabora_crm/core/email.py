"""Email sending via Brevo's transactional HTTP API (POST /v3/smtp/email).

Uses urllib so no extra dependency is required.
Raises EmailSendError on any failure — callers decide whether to surface it.
"""
import json
import logging
import urllib.error
import urllib.request

from nabora_crm.core.config import settings
from nabora_crm.core.exceptions import EmailSendError

logger = logging.getLogger("nabora_crm")

_BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _build_invitation_html(invite_link: str, inviter_name: str | None = None) -> str:
    greeter = f"{inviter_name} has invited you" if inviter_name else "You have been invited"
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Welcome to Nabora CRM</h2>
        <p>{greeter} to join <strong>Nabora CRM</strong>.</p>
        <p>Click the button below to set up your password and activate your account:</p>
        <p>
          <a href="{invite_link}"
             style="display:inline-block;padding:12px 24px;background:#4F46E5;
                    color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
            Set Up My Password
          </a>
        </p>
        <p style="color:#888;font-size:0.9em;">
          This link expires in {settings.INVITATION_TOKEN_EXPIRE_DAYS} day(s).
          If you did not expect this email, you can safely ignore it.
        </p>
        <hr/>
        <p style="font-size:0.85em;color:#aaa;">
          If the button does not work, paste this URL into your browser:<br/>
          <a href="{invite_link}">{invite_link}</a>
        </p>
      </body>
    </html>
    """


def _build_invitation_text(invite_link: str, inviter_name: str | None = None) -> str:
    greeter = f"{inviter_name} has invited you" if inviter_name else "You have been invited"
    return (
        f"{greeter} to join Nabora CRM.\n\n"
        f"Set up your password by visiting the link below:\n{invite_link}\n\n"
        f"This link expires in {settings.INVITATION_TOKEN_EXPIRE_DAYS} day(s).\n"
        "If you did not expect this email, you can safely ignore it."
    )


def _build_password_reset_html(reset_link: str) -> str:
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Reset your Nabora CRM password</h2>
        <p>We received a request to reset your password.</p>
        <p>Click the button below to choose a new password:</p>
        <p>
          <a href="{reset_link}"
             style="display:inline-block;padding:12px 24px;background:#4F46E5;
                    color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
            Reset My Password
          </a>
        </p>
        <p style="color:#888;font-size:0.9em;">
          This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minute(s).
          If you did not request a password reset, you can safely ignore this email.
        </p>
        <hr/>
        <p style="font-size:0.85em;color:#aaa;">
          If the button does not work, paste this URL into your browser:<br/>
          <a href="{reset_link}">{reset_link}</a>
        </p>
      </body>
    </html>
    """


def _build_password_reset_text(reset_link: str) -> str:
    return (
        "We received a request to reset your Nabora CRM password.\n\n"
        f"Choose a new password by visiting the link below:\n{reset_link}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minute(s).\n"
        "If you did not request a password reset, you can safely ignore this email."
    )


def _send_email(
    *,
    to_email: str,
    to_name: str | None,
    subject: str,
    html_content: str,
    text_content: str,
    label: str,
) -> None:
    """Send one transactional email via Brevo, raising EmailSendError on failure."""
    if not settings.BREVO_API_KEY:
        raise EmailSendError(
            "Brevo API key is not configured. Set BREVO_API_KEY in your environment."
        )

    from_email = settings.EMAIL_FROM or "noreply@nabora.app"

    payload = {
        "sender": {"name": "Nabora CRM", "email": from_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
        "textContent": text_content,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _BREVO_API_URL,
        data=body,
        headers={
            "api-key": settings.BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        logger.info("%s email sent to %s via Brevo API", label, to_email)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "Brevo API error sending %s to %s: %s %s — %s",
            label, to_email, exc.code, exc.reason, body_text,
        )
        raise EmailSendError(
            f"Failed to send {label} email: {exc.code} {exc.reason} — {body_text}"
        ) from exc
    except urllib.error.URLError as exc:
        logger.error("Brevo API unreachable sending %s to %s: %s", label, to_email, exc.reason)
        raise EmailSendError(
            f"Failed to send {label} email: {exc.reason}"
        ) from exc


def send_invitation_email(
    *,
    to_email: str,
    invite_token: str,
    to_name: str | None = None,
    inviter_name: str | None = None,
) -> None:
    """Send an invitation email via Brevo's HTTP API.

    Args:
        to_email:     Recipient email address.
        invite_token: Short-lived JWT to embed in the setup link.
        to_name:      Recipient display name (optional).
        inviter_name: Sender's name shown in the email body (optional).

    Raises:
        EmailSendError: If BREVO_API_KEY is not set or the request fails.
    """
    invite_link = f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/accept-invite?token={invite_token}"
    _send_email(
        to_email=to_email,
        to_name=to_name,
        subject="You're invited to Nabora CRM — set up your account",
        html_content=_build_invitation_html(invite_link, inviter_name),
        text_content=_build_invitation_text(invite_link, inviter_name),
        label="invitation",
    )


def send_password_reset_email(
    *,
    to_email: str,
    reset_token: str,
    to_name: str | None = None,
) -> None:
    """Send a password reset email via Brevo's HTTP API.

    Raises:
        EmailSendError: If BREVO_API_KEY is not set or the request fails.
    """
    reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/reset-password?token={reset_token}"
    _send_email(
        to_email=to_email,
        to_name=to_name,
        subject="Reset your Nabora CRM password",
        html_content=_build_password_reset_html(reset_link),
        text_content=_build_password_reset_text(reset_link),
        label="password reset",
    )
