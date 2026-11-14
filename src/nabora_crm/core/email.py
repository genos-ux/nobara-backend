"""Email sending service.

Uses Python's built-in smtplib so no extra dependency is required.
Wrap calls in a try/except at the call site — EmailSendError is raised
on any SMTP failure so the caller can decide whether to surface it.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from nabora_crm.core.config import settings
from nabora_crm.core.exceptions import EmailSendError

logger = logging.getLogger("nabora_crm")


def _build_invitation_html(invite_link: str, inviter_name: str | None = None) -> str:
    """Return the HTML body for an invitation email."""
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
    """Return the plain-text body for an invitation email."""
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
    inviter_name: str | None = None,
) -> None:
    """Send an invitation email to `to_email` with a password-setup link.

    The link points to ``{FRONTEND_URL}/setup-password?token=<token>``.

    Raises:
        EmailSendError: If the SMTP configuration is missing or the email
                        could not be delivered.
    """
    if not settings.SMTP_HOST:
        raise EmailSendError(
            "SMTP is not configured. Set SMTP_HOST in your environment."
        )

    invite_link = f"{settings.FRONTEND_URL.rstrip('/')}/setup-password?token={invite_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "You're invited to Nabora CRM — set up your account"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USERNAME
    msg["To"] = to_email

    msg.attach(MIMEText(_build_invitation_text(invite_link, inviter_name), "plain"))
    msg.attach(MIMEText(_build_invitation_html(invite_link, inviter_name), "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        logger.info("Invitation email sent to %s", to_email)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send invitation email to %s: %s", to_email, exc)
        raise EmailSendError(f"Failed to send invitation email: {exc}") from exc
