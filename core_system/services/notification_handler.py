from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

from django.conf import settings
from django.utils import timezone

from core_system.models import Notification


@dataclass(frozen=True)
class GmailSMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True


def get_gmail_smtp_config() -> Optional[GmailSMTPConfig]:
    """Read Gmail SMTP configuration from Django settings.

    Add these to `caufa_portal/settings.py`:
      - GMAIL_SMTP_HOST
      - GMAIL_SMTP_PORT
      - GMAIL_SMTP_USER
      - GMAIL_SMTP_PASSWORD
      - GMAIL_SMTP_USE_TLS (optional, default True)

    Returns None if required vars are missing.
    """

    host = getattr(settings, "GMAIL_SMTP_HOST", None)
    port = getattr(settings, "GMAIL_SMTP_PORT", None)
    user = getattr(settings, "GMAIL_SMTP_USER", None)
    password = getattr(settings, "GMAIL_SMTP_PASSWORD", None)

    if not (host and port and user and password):
        return None

    return GmailSMTPConfig(
        host=str(host),
        port=int(port),
        username=str(user),
        password=str(password),
        use_tls=bool(getattr(settings, "GMAIL_SMTP_USE_TLS", True)),
    )


def send_email_gmail_smtp(*, to_email: str, subject: str, body: str) -> None:
    """Send an email via Gmail SMTP.

    If SMTP settings are not configured, this function becomes a no-op.
    """

    config = get_gmail_smtp_config()
    if config is None:
        return

    msg = EmailMessage()
    msg["From"] = config.username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if config.use_tls:
        server = smtplib.SMTP(config.host, config.port)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(config.host, config.port)

    try:
        server.login(config.username, config.password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def queue_and_send_member_notification(
    *,
    member,
    message: str,
    notification_type: str,
) -> Notification:
    """Create Notification row and optionally send email (best-effort).

    - Uses `member.email` as recipient_contact.
    - If email not present, it will still create the Notification row.
    """

    to_email = getattr(member, "email", None) or None

    notif = Notification.objects.create(
        recipient_type="Member",
        recipient_id=int(member.member_id_PK),
        recipient_name=getattr(member, "full_name", ""),
        recipient_contact=to_email,
        notification_type=notification_type,
        message=message,
        delivery_status="Queued",
    )

    if to_email:
        try:
            send_email_gmail_smtp(
                to_email=to_email,
                subject=notification_type,
                body=message,
            )
            notif.delivery_status = "Sent"
        except Exception:
            notif.delivery_status = "Failed"

        notif.save(update_fields=["delivery_status"])

    return notif


