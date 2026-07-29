from __future__ import annotations

import base64
import logging
from email.mime.image import MIMEImage
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import connection
from django.template.loader import render_to_string
from django.utils import timezone

from core_system.constants.policy_constants import (
    get_membership_fee_amount,
    get_monthly_dues_amount,
)
from core_system.models import Member

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)


def _get_logo_data_uri(max_width: int = 120) -> str | None:
    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "isu_caufa_official.png"
    if not logo_path.exists():
        logger.warning("Logo file not found at %s", logo_path)
        return None
    if HAS_PIL:
        try:
            img = Image.open(logo_path)
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (27, 94, 32))
                bg.paste(img, mask=img.split()[3])
                img = bg
            w_percent = max_width / float(img.size[0])
            new_h = int(float(img.size[1]) * float(w_percent))
            img = img.resize((max_width, new_h), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            logger.info("Email logo embedded as data URI (%d bytes)", len(buf.getvalue()))
            return f"data:image/jpeg;base64,{b64}"
        except Exception as exc:
            logger.warning("PIL logo resize failed: %s", exc)
    try:
        with open(logo_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("ascii")
        logger.warning("Email logo embedded as raw base64 PNG (%d bytes)", len(data))
        return f"data:image/png;base64,{b64}"
    except Exception as exc:
        logger.error("Failed to read logo file: %s", exc)
        return None


def send_html_email(
    subject: str,
    recipient_list: list[str],
    html_template: str,
    context: dict | None = None,
    from_email: str | None = None,
) -> bool:
    if not recipient_list:
        return False

    html_content = render_to_string(html_template, context or {})

    text_content = f"""
{subject}

---
This email was sent by ISU CAUFA.
"""

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    msg.attach_alternative(html_content, "text/html")

    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "isu_caufa_official.png"
    if logo_path.exists():
        try:
            with open(logo_path, "rb") as f:
                logo_data = f.read()
            image = MIMEImage(logo_data)
            image.add_header("Content-ID", "<logo_cid>")
            image.add_header("Content-Disposition", "inline", filename="isu_caufa_official.png")
            msg.attach(image)
        except Exception:
            pass

    try:
        msg.send(fail_silently=False)
        logger.info("Email sent to %s: %s", ", ".join(recipient_list), subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", ", ".join(recipient_list), exc)
        return False


def send_member_added_email(member, officer_contact: str | None = None) -> bool:
    if not member.email:
        return False

    context = {
        "full_name": member.full_name,
        "employee_id": member.employee_id or "N/A",
        "date_joined": member.date_joined.strftime("%B %d, %Y") if member.date_joined else str(timezone.now().date()),
        "department": member.department or "",
        "monthly_dues_amount": get_monthly_dues_amount(),
        "membership_fee_amount": get_membership_fee_amount(),
        "officer_contact": officer_contact or "",
    }

    return send_html_email(
        subject="Welcome to ISU CAUFA – Membership Registration Confirmed",
        recipient_list=[member.email],
        html_template="emails/member_added.html",
        context=context,
    )


def send_registration_received_email(email: str, full_name: str, employee_id: str) -> bool:
    if not email:
        return False
    return send_html_email(
        subject="Registration Received – ISU CAUFA Membership",
        recipient_list=[email],
        html_template="emails/registration_received.html",
        context={
            "full_name": full_name,
            "employee_id": employee_id or "N/A",
        },
    )


def send_registration_status_update_email(email: str, full_name: str, new_status: str, next_stage: str) -> bool:
    if not email:
        return False
    return send_html_email(
        subject="Registration Update – ISU CAUFA",
        recipient_list=[email],
        html_template="emails/registration_status_update.html",
        context={
            "full_name": full_name,
            "new_status": new_status,
            "next_stage": next_stage,
        },
    )


def send_registration_returned_email(email: str, full_name: str, reason: str) -> bool:
    if not email:
        return False
    return send_html_email(
        subject="Registration Returned for Revision – ISU CAUFA",
        recipient_list=[email],
        html_template="emails/registration_returned.html",
        context={
            "full_name": full_name,
            "reason": reason,
        },
    )


def send_registration_rejected_email(email: str, full_name: str, reason: str = "") -> bool:
    if not email:
        return False
    return send_html_email(
        subject="Registration Status – ISU CAUFA",
        recipient_list=[email],
        html_template="emails/registration_rejected.html",
        context={
            "full_name": full_name,
            "reason": reason,
        },
    )


def send_aid_processing_notice(member, aid_type: str) -> bool:
    if not member or not member.email:
        return False

    context = {
        "member_name": member.full_name,
    }

    return send_html_email(
        subject="Notice of Aid Processing",
        recipient_list=[member.email],
        html_template="emails/aid_processing_notice.html",
        context=context,
    )


def send_aid_bulk_contribution_notice(contribution_amount: float, aid_type: str, exclude_member=None) -> bool:
    members = Member.objects.exclude(membership_status__iexact="Retired")
    if exclude_member:
        members = members.exclude(member_id_PK=exclude_member.member_id_PK)

    recipient_emails = list(
        members.exclude(email__isnull=True).exclude(email__exact="").values_list("email", flat=True)
    )
    if not recipient_emails:
        return False

    context = {
        "contribution_amount": f"{contribution_amount:,.2f}",
    }

    return send_html_email(
        subject="Notice of Active Member Contribution",
        recipient_list=recipient_emails,
        html_template="emails/aid_bulk_contribution_notice.html",
        context=context,
    )


# ---------------------------------------------------------------------------
# Email Queue (fast, non-blocking — replaces threading.Thread)
# ---------------------------------------------------------------------------


def queue_email(subject, recipient_list, html_template, context=None):
    from core_system.models import OutgoingEmail

    return OutgoingEmail.objects.create(
        recipient_list=recipient_list,
        subject=subject,
        html_template=html_template,
        context=context or {},
    )


def send_aid_emails(record, table_name, per_member_amount):
    """Send both aid emails synchronously (private + bulk)."""
    from core_system.models import Member

    if record.member_id_FK and record.member_id_FK.email:
        send_html_email(
            subject="Notice of Aid Processing",
            recipient_list=[record.member_id_FK.email],
            html_template="emails/aid_processing_notice.html",
            context={"member_name": record.member_id_FK.full_name},
        )

    members = Member.objects.exclude(membership_status__iexact="Retired")
    recipient_emails = list(
        members.exclude(email__isnull=True).exclude(email__exact="").values_list("email", flat=True)
    )
    if recipient_emails:
        send_html_email(
            subject="Notice of Active Member Contribution",
            recipient_list=recipient_emails,
            html_template="emails/aid_bulk_contribution_notice.html",
            context={
                "contribution_amount": f"{per_member_amount:,.2f}",
            },
        )


def _send_queued_email(email_record):
    from core_system.models import OutgoingEmail, Member

    if email_record.html_template == "emails/aid_bulk_contribution_notice.html":
        members = Member.objects.exclude(membership_status__iexact="Retired")
        email_record.recipient_list = list(
            members.exclude(email__isnull=True).exclude(email__exact="").values_list("email", flat=True)
        )

    send_html_email(
        subject=email_record.subject,
        recipient_list=email_record.recipient_list,
        html_template=email_record.html_template,
        context=email_record.context,
    )
    email_record.status = OutgoingEmail.SENT
    email_record.sent_at = timezone.now()
    email_record.save(update_fields=["status", "sent_at"])


def process_email_queue(batch_size=5):
    """Send pending emails sequentially. Safe to call from any context."""
    from core_system.models import OutgoingEmail

    pending = OutgoingEmail.objects.filter(status=OutgoingEmail.PENDING).order_by("created_at")[:batch_size]
    if not pending:
        return 0

    sent_count = 0
    for email in pending:
        try:
            _send_queued_email(email)
            sent_count += 1
        except Exception as exc:
            email.status = OutgoingEmail.FAILED
            email.error_message = str(exc)
            email.retry_count += 1
            email.save(update_fields=["status", "error_message", "retry_count"])
            logger.error("Failed to send queued email %s: %s", email.outgoing_email_id, exc)

    connection.close()
    return sent_count
