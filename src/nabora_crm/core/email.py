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
    if not settings.BREVO_API_KEY:
        raise EmailSendError(
            "Brevo API key is not configured. Set BREVO_API_KEY in your environment."
        )

    invite_link = f"{settings.FRONTEND_URL.rstrip('/')}/setup-password?token={invite_token}"

    from_email = settings.EMAIL_FROM or "noreply@nabora.app"

    payload = {
        "sender": {"name": "Nabora CRM", "email": from_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": "You're invited to Nabora CRM — set up your account",
        "htmlContent": _build_invitation_html(invite_link, inviter_name),
        "textContent": _build_invitation_text(invite_link, inviter_name),
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
        logger.info("Invitation email sent to %s via Brevo API", to_email)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "Brevo API error sending to %s: %s %s — %s",
            to_email, exc.code, exc.reason, body_text,
        )
        raise EmailSendError(
            f"Failed to send invitation email: {exc.code} {exc.reason} — {body_text}"
        ) from exc
    except urllib.error.URLError as exc:
        logger.error("Brevo API unreachable sending to %s: %s", to_email, exc.reason)
        raise EmailSendError(
            f"Failed to send invitation email: {exc.reason}"
        ) from exc
