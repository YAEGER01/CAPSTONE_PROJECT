from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from core_system.constants.policy_constants import (
    get_membership_fee_amount,
    get_monthly_dues_amount,
)
from core_system.models import Member

logger = logging.getLogger(__name__)


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

    logo_path = Path(settings.BASE_DIR) / "static" / "images" / "isu_caufa_official.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo_cid>")
        image.add_header("Content-Disposition", "inline", filename="isu_caufa_official.png")
        msg.attach(image)

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
