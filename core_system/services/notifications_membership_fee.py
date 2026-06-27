from __future__ import annotations

from core_system.models import Member
from core_system.services.notification_handler import queue_and_send_member_notification


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


