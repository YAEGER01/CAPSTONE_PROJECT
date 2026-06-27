from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType

from core_system.models import (
    AuditLog,
    FinancialDocumentArchive,
    MembershipFee,
    OfficerUser,
    RevisionLog,
    TransactionVerification,
)


@dataclass(frozen=True)
class MembershipFeeCorrectionContext:
    fee: MembershipFee
    officer: OfficerUser
    validation_errors: list[str]


def create_correction_artifacts_for_membership_fee(
    *,
    fee: MembershipFee,
    officer: OfficerUser,
    validation_errors: list[str],
    request,
) -> None:
    """Create the audit artifacts for Treasurer-side validation failure.

    This is Option A from TODO.md:
    - keep a MembershipFee row (so Auditor has something to review)
    - set TransactionVerification to 'Returned for Revision'
    - create RevisionLog snapshot + reason
    - create a FinancialDocumentArchive placeholder (AuditLog needs FK)
    - write AuditLog entry
    """

    # 1) Set verification status
    TransactionVerification.objects.filter(
        table_name="membership_fee",
        record_id=fee.fee_id_PK,
    ).update(
        verification_status="Returned for Revision",
    )

    # 2) RevisionLog
    # Snapshot minimal fields we already have access to.
    snapshot: dict[str, Any] = {
        "fee_id": fee.fee_id_PK,
        "member_id_FK": fee.member_id_FK_id,
        "receipt_number": fee.receipt_number,
        "amount": str(fee.amount),
        "month_covered": fee.month_covered,
        "payment_date": str(fee.payment_date),
        "payment_method": fee.payment_method,
        "payment_status": fee.payment_status,
        "deposit_reference": fee.deposit_reference,
    }

    RevisionLog.objects.create(
        content_type=ContentType.objects.get_for_model(MembershipFee),
        object_id=fee.pk,
        rejection_reason="Payment requires correction: " + "; ".join(validation_errors),
        snapshot_data=snapshot,
        auditor_id_FK=None,  # auditor is not known here; leave NULL
    )

    # 3) Placeholder archive (AuditLog.entity_id is FK to FinancialDocumentArchive)
    archive = FinancialDocumentArchive.objects.create(
        related_module="MEMBERSHIP_FEE",
        related_record_id=fee.fee_id_PK,
        document_type="treasurer_validation_correction",
        file_path="",
        file_hash="",
        verification_status="Returned for Revision",
        uploaded_by_user_id_FK=officer,
    )

    # 4) AuditLog
    AuditLog.objects.create(
        actor_type="Treasurer",
        actor_id=officer.user_id_PK,
        action="Membership fee validation correction required",
        entity_type="MembershipFee",
        entity_id=archive,
        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        device_info="",
    )

    return


