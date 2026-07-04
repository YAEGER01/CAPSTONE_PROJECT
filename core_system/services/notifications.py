from __future__ import annotations

import smtplib
import threading
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

from django.conf import settings
from django.utils import timezone

from core_system.models import Member, Notification


# ==========================================================================
# LOW-LEVEL — notification_handler.py merged here
# ==========================================================================

@dataclass(frozen=True)
class GmailSMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True


def get_gmail_smtp_config() -> Optional[GmailSMTPConfig]:
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
        notif_pk = notif.notification_id_PK

        def _send_async():
            try:
                send_email_gmail_smtp(
                    to_email=to_email,
                    subject=notification_type,
                    body=message,
                )
                Notification.objects.filter(notification_id_PK=notif_pk).update(
                    delivery_status="Sent"
                )
            except Exception:
                Notification.objects.filter(notification_id_PK=notif_pk).update(
                    delivery_status="Failed"
                )

        threading.Thread(target=_send_async, daemon=True).start()

    return notif


# ==========================================================================
# HIGH-LEVEL WRAPPERS — notifications_membership_fee.py merged here
# ==========================================================================

def notify_membership_fee_policy_exception(*, member: Member, reason: str) -> None:
    queue_and_send_member_notification(
        member=member,
        notification_type="Membership Fee Policy Exception",
        message=f"Membership fee entry was not required for your account. Reason: {reason}",
    )


def notify_membership_fee_correction_required(*, member: Member) -> None:
    queue_and_send_member_notification(
        member=member,
        notification_type="Membership Fee Correction Required",
        message="Your membership fee payment requires correction. Please review and resubmit via the Treasurer workflow.",
    )


def notify_membership_fee_confirmed(*, member: Member) -> None:
    queue_and_send_member_notification(
        member=member,
        notification_type="Membership Fee Payment Confirmed",
        message=(
            "Your membership fee payment has been received and submitted for audit verification."
        ),
    )
