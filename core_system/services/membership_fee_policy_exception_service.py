from __future__ import annotations

from core_system.models import AuditLog, Member, OfficerUser, FinancialDocumentArchive, TransactionVerification
from core_system.models import Notification  # noqa: F401
from core_system.services.notifications_membership_fee import notify_membership_fee_policy_exception


def record_membership_fee_policy_exception(*, member: Member, reason: str, officer: OfficerUser, request) -> None:
    """Persist a policy exception outcome for a membership-fee attempt.

    There is currently no dedicated MembershipFeePolicyException model in this repo.
    We model the exception as a TransactionVerification row placeholder + AuditLog entry.

    This keeps the implementation self-contained without schema changes.
    """

    # Create an empty archive row so AuditLog has a valid FK.
    archive = FinancialDocumentArchive.objects.create(
        related_module="MEMBERSHIP_FEE",
        related_record_id=member.member_id_PK,
        document_type="treasurer_policy_exception",
        file_path="",
        file_hash="",
        verification_status="Policy Exception",
        uploaded_by_user_id_FK=officer,
    )

    # Write AuditLog
    AuditLog.objects.create(
        actor_type="Treasurer",
        actor_id=officer.user_id_PK,
        action="Membership fee policy exception recorded",
        entity_type="MembershipFee",
        entity_id=archive,
        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        device_info="",
    )

    # Notify member (already persists Notification row)
    notify_membership_fee_policy_exception(member=member, reason=reason)

