from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from core_system.constants.policy_constants import (
    get_death_aid_amount,
    get_expected_dues_amount,
    get_membership_fee_amount,
    get_monthly_dues_amount,
)
from core_system.guards import require_role
from core_system.models import (
    AuditLog,
    FinancialDocumentArchive,
    MembershipFee,
    MonthlyDues,
    MedicalAid,
    DeathAid,
    OfficerUser,
    TransactionVerification,
    RevisionLog,
    SupportingProof,
    AuditorPaymentVerification,
    AuditorAidVerification,
)
from django.contrib.contenttypes.models import ContentType
from django.db import transaction


MODEL_MAP = {
    "membership_fee": MembershipFee,
    "monthly_dues": MonthlyDues,
    "medical_aid": MedicalAid,
    "death_aid": DeathAid,
}


# def _serialize_record(instance) -> Dict[str, Any]:
#    """Serialize model instance to JSON-compatible dict."""
#    return {field.name: getattr(instance, field.name) for field in instance.#_meta.fields}
from django.db.models import ForeignKey
from typing import Dict, Any


def _serialize_record(instance) -> Dict[str, Any]:
    """Serialize model instance to JSON-compatible dict."""
    data = {}
    for field in instance._meta.fields:
        value = getattr(instance, field.name)

        # If the field is a ForeignKey, save the database ID instead of the object
        if isinstance(field, ForeignKey) and value is not None:
            data[field.name] = value.pk
        else:
            # For decimals/dates/datetimes, convert them to strings so JSON doesn't complain
            if hasattr(value, "isoformat"):  # Handles dates and datetimes
                data[field.name] = value.isoformat()
            elif (
                hasattr(value, "to_eng_string") or type(value).__name__ == "Decimal"
            ):  # Handles Decimal amounts
                data[field.name] = str(value)
            else:
                data[field.name] = value

    return data


def _get_officer_from_session(request: HttpRequest) -> Optional[OfficerUser]:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return None
    try:
        return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except Exception:
        return None


def _file_upload_to_archive(
    *,
    request: HttpRequest,

    related_module: str,
    related_record_id: int,
    document_type: str,
    uploaded_file,
    verification_status: str,
) -> FinancialDocumentArchive:
    """Stores uploaded evidence file and creates a FINANCIAL_DOCUMENT_ARCHIVE row."""
    # Store using Django default storage
    filename = uploaded_file.name
    stored_name = default_storage.save(
        f"evidence_uploads/{timezone.now().strftime('%Y%m%d')}_{filename}",
        uploaded_file,
    )

    # Best-effort hash (don't fail if hashing fails)
    file_hash = ""
    try:
        hasher = hashlib.sha256()
        # UploadedFile may not support seek; attempt read then reset
        data = uploaded_file.read()
        hasher.update(data)
        file_hash = hasher.hexdigest()
    except Exception:
        file_hash = ""

    officer = _get_officer_from_session(request)
    if officer is None:
        # caller should ensure authenticated by role guard
        raise ValueError("Officer session missing")

    archive = FinancialDocumentArchive.objects.create(
        related_module=related_module,
        related_record_id=related_record_id,
        document_type=document_type,
        file_path=stored_name,
        file_hash=file_hash or "",
        verification_status=verification_status,
        uploaded_by_user_id_FK=officer,
    )
    return archive


def _create_placeholder_archive(
    *,
    request: HttpRequest,
    related_module: str,
    related_record_id: int,
    document_type: str,
    verification_status: str,
) -> FinancialDocumentArchive:
    """Creates an archive row even when no file was uploaded.

    AuditLog.entity_id requires a FINANCIAL_DOCUMENT_ARCHIVE FK, so we must create one.
    """
    officer = _get_officer_from_session(request)
    if officer is None:
        raise ValueError("Officer session missing")

    # file_path can be empty string
    return FinancialDocumentArchive.objects.create(
        related_module=related_module,
        related_record_id=related_record_id,
        document_type=document_type,
        file_path="",
        file_hash="",
        verification_status=verification_status,
        uploaded_by_user_id_FK=officer,
    )


PAYMENT_SOURCE_LABELS = {
    "membership_fee": "Membership Fee",
    "monthly_dues": "Monthly Dues",
}


def _payment_type_label(kind: str, obj: Any) -> str:
    if kind == "monthly_dues":
        method = str(getattr(obj, "payment_method", "") or "").strip()
        if method.lower() == "salary deduction":
            return "Salary Deduction"
    return "OTC Payment"


def _payment_item_to_json(kind: str, obj: Any) -> Dict[str, Any]:
    # kind in: 'membership_fee' | 'monthly_dues'
    member = getattr(obj, "member_id_FK", None)

    amount = getattr(obj, "amount", None)
    payment_date = getattr(obj, "payment_date", None)
    payment_method = getattr(obj, "payment_status", None) if kind == "membership_fee" else getattr(obj, "payment_method", None)

    # For MonthlyDues, expected UI label is: month_covered, payment_method, payment_date is not present.
    month_covered = getattr(obj, "month_covered", None)

    # UI expects: memberName, facultyId, department, position, contact, email, membership_status.
    expected_amount = (
        get_membership_fee_amount()
        if kind == "membership_fee"
        else get_monthly_dues_amount()
    )

    return {
        "id": str(obj.fee_id_PK if kind == "membership_fee" else obj.dues_id_PK),
        "entity_id": int(obj.fee_id_PK if kind == "membership_fee" else obj.dues_id_PK),
        "source": kind,
        "source_label": PAYMENT_SOURCE_LABELS.get(kind, kind.replace("_", " ").title()),
        "payment_type": _payment_type_label(kind, obj),
        "type": "OTC Fee Payment" if kind == "membership_fee" else "Monthly Dues",
        "ref": (getattr(obj, "remittance_reference", None) or getattr(obj, "receipt_number", None) or "") if kind == "monthly_dues" else (getattr(obj, "receipt_number", None) or ""),
        "member": {
            "member_id": member.member_id_PK if member else None,
            "member_name": member.full_name if member else "",
                        "employee_id": member.employee_id or "" if member else "",

            "department": member.department or "" if member else "",
            "position": member.position or "" if member else "",
            "contact": getattr(member, "contact_number", None) or "",
            "email": getattr(member, "email", None) or "",
            "membership_status": getattr(member, "membership_status", None) or "",
        },
        "amount": str(amount) if amount is not None else "0",
        "expected": str(expected_amount),
        "month": month_covered or "N/A",
        "date": str(payment_date) if payment_date is not None else "",
        "method": str(payment_method) if payment_method is not None else "",
        "encoded_by": getattr(getattr(obj, "recorded_by_user_id_FK", None), "full_name", "") or "",
        "payment_status": getattr(obj, "payment_status", None) or "",
    }


@require_GET
def president_auditor_approved_payments_queue(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    approved_verifications = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related()

    items: List[Dict[str, Any]] = []

    for tv in approved_verifications:
        if str(tv.table_name).lower() == "membership_fee":
            fee = (
                MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
                .filter(fee_id_PK=tv.record_id)
                .first()
            )
            if not fee:
                continue
            items.append(_payment_item_to_json("membership_fee", fee))
        elif str(tv.table_name).lower() == "monthly_dues":
            dues = (
                MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
                .filter(dues_id_PK=tv.record_id)
                .first()
            )
            if not dues:
                continue
            items.append(_payment_item_to_json("monthly_dues", dues))

    items.sort(key=lambda x: x.get("entity_id", 0), reverse=True)
    return JsonResponse({"ok": True, "payments": items})


@require_GET
def president_auditor_approved_payment_detail(request: HttpRequest, entity_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    # entity_id can belong to either MembershipFee or MonthlyDues.
    fee = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").filter(fee_id_PK=entity_id).first()
    dues = MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK").filter(dues_id_PK=entity_id).first()

    tv = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        record_id=entity_id,
        verification_status="Auditor Verified",
        president_id_FK__isnull=True,
    ).order_by("-approved_at", "-verified_at").first()

    if not tv or (not fee and not dues):
        return JsonResponse({"ok": False, "error": "Approved payment not found."}, status=404)

    # Approved blocks
    approved_membership = None
    approved_otc_dues = None
    approved_salary_dues = None

    if fee:
        approved_membership = _payment_item_to_json("membership_fee", fee)

    if dues:
        # Split OTC vs Salary Deduction based on payment_method
        method = (dues.payment_method or "").lower()
        if method == "salary deduction":
            approved_salary_dues = _payment_item_to_json("monthly_dues", dues)
        else:
            approved_otc_dues = _payment_item_to_json("monthly_dues", dues)

    # Auditor summary notes / evidence
    auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else ""
    auditor_date = (tv.verified_at.isoformat() if tv.verified_at else "")

    evidence_filename = ""
    # Use FinancialDocumentArchive's last auditor_finding for this record_id.
    archive = FinancialDocumentArchive.objects.filter(
        related_record_id=entity_id,
        document_type="auditor_finding",
        related_module=tv.table_name.upper(),
    ).order_by("-uploaded_at").first()
    if archive and archive.file_path:
        evidence_filename = archive.file_path.split("/")[-1]

    remarks_text = "—"
    # If there was a Return for Revision, RevisionLog will store rejection_reason.
    # For now, we default to '—' because the approve-flow does not persist auditor remarks.
    # (If you later add a dedicated auditor remarks field, we can wire it here.)

    detail_payload = {
        "ok": True,
        "item": {
            "id": str(entity_id),
            "table_name": tv.table_name,
            "auditorName": auditor_name,
            "auditorDate": auditor_date,
            "auditorEvidence": evidence_filename or "",
            "auditorRemarks": remarks_text,
        },
        "approvedMembership": approved_membership,
        "approvedOtcDues": approved_otc_dues,
        "approvedSalaryDues": approved_salary_dues,
        "treasurerOriginal": {
            "member": None,
        },
    }

    # Also return Treasurer original entry fields from the same models.
    if fee:
        detail_payload["treasurerOriginal"] = {
            "memberName": fee.member_id_FK.full_name,
            "employeeId": fee.member_id_FK.employee_id or "",
            "department": fee.member_id_FK.department or "",
            "status": fee.member_id_FK.membership_status or "",
            "contact": fee.member_id_FK.contact_number or "",
            "covered": fee.month_covered or "",
            "expected": str(fee.amount),
            "method": fee.payment_method or "",
            "ref": fee.receipt_number or "",
            "encoder": getattr(fee.recorded_by_user_id_FK, "full_name", "") or "",
        }
    elif dues:
        detail_payload["treasurerOriginal"] = {
            "memberName": dues.member_id_FK.full_name,
            "employeeId": dues.member_id_FK.employee_id or "",
            "department": dues.member_id_FK.department or "",
            "status": dues.member_id_FK.membership_status or "",
            "contact": dues.member_id_FK.contact_number or "",
            "covered": dues.month_covered or "",
            "expected": str(dues.amount),
            "method": dues.payment_method or "",
            "ref": dues.receipt_number or dues.remittance_reference or "",
            "encoder": getattr(dues.recorded_by_user_id_FK, "full_name", "") or "",
        }

    # For now timeline is not implemented server-side; UI currently uses demo timelines.
    # Keep payload compatible with existing UI if timeline is optional.
    detail_payload["timeline"] = []

    return JsonResponse(detail_payload)


@require_GET
def auditor_pending_payments(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    # Get all pending verifications from transaction_verification table
    pending_verifications = TransactionVerification.objects.filter(
        verification_status="Pending",
        auditor_id_FK__isnull=True,
    ).select_related().all()

    # Extract record_ids grouped by table_name
    pending_fee_ids = set()
    pending_dues_ids = set()

    for tv in pending_verifications:
        if str(tv.table_name).lower() == "membership_fee":
            pending_fee_ids.add(tv.record_id)
        elif str(tv.table_name).lower() == "monthly_dues":
            pending_dues_ids.add(tv.record_id)

    # Also include records that have no verification entry yet (treat as pending)
    all_fees = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").all()
    all_dues = MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK").all()

    items: List[Dict[str, Any]] = []

    for f in all_fees:
        # Include if pending verification or no verification exists
        if f.fee_id_PK in pending_fee_ids:
            items.append(_payment_item_to_json("membership_fee", f))

    for d in all_dues:
        if d.dues_id_PK in pending_dues_ids:
            items.append(_payment_item_to_json("monthly_dues", d))

    # Sort by most recent first
    items.sort(key=lambda x: x.get("entity_id", 0), reverse=True)

    return JsonResponse({"ok": True, "payments": items})


@require_GET
def auditor_pending_aids(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    medicals = MedicalAid.objects.select_related(
        "member_id_FK",
        "auditor_verified_by_user_id_FK",
        "treasurer_validated_by_user_id_FK",
        "president_decided_by_user_id_FK",
    ).order_by("-medical_aid_id_PK")

    deaths = DeathAid.objects.select_related(
        "member_id_FK",
        "claimant_id_FK",
        "treasurer_validated_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
        "president_decided_by_user_id_FK",
    ).order_by("-death_aid_id_PK")

    items: List[Dict[str, Any]] = []

    pending_aid_statuses = {
        "Pending",
        "Pending Verification",
        "Pending Treasurer Check",
    }


    for m in medicals:
        if str(m.status) in pending_aid_statuses:
            member = m.member_id_FK
            items.append(
                {
                    "id": "medical-" + str(m.medical_aid_id_PK),
                    "entity_id": int(m.medical_aid_id_PK),
                    "aid_type": "medical_aid",
                    "type": "Medical Aid Request",
                    "request_date": str(m.request_date),
                    "medical_case": m.document_status or m.policy_record_status or "",
                    "requested_amount": str(m.requested_amount),
                    "hospital": m.hospital_name or (member.full_name if member else ""),
                    "total_hospital_bill": str(m.hospital_bill_amount),
                    "validated_aid_amount": str(m.validated_aid_amount),
                    "treasurer_validation": m.document_status or m.policy_record_status or "",
                    "date": str(m.request_date),
                    "reqAmount": str(m.validated_aid_amount or m.requested_amount),
                    "bill": str(m.hospital_bill_amount),
                    "reason": m.document_status or m.policy_record_status or "",
                    "validation": m.document_status or m.policy_record_status or "",
                    "member": {
                        "member_id": member.member_id_PK,
                        "member_name": member.full_name,
                        "employee_id": member.employee_id or "",
                        "department": member.department or "",
                        "position": member.position or "",
                        "contact": member.contact_number or "",
                        "email": member.email or "",
                    },
                }
            )

    for d in deaths:
        if str(d.status) in pending_aid_statuses:
            member = d.member_id_FK
            claimant = d.claimant_id_FK
            items.append(
                {
                    "id": "death-" + str(d.death_aid_id_PK),
                    "entity_id": int(d.death_aid_id_PK),
                    "aid_type": "death_aid",
                    "type": "Death Aid Claim",
                    "claim_date": str(d.claim_date),
                    "deceased_name": d.deceased_name,
                    "relationship": d.relationship_to_member,
                    "claim_type": d.claim_type,
                    "claimant_name": claimant.full_name if claimant else "",
                    "claimant_contact": claimant.contact_number if claimant else "",
                    "benefit_amount": str(d.benefit_amount),
                    "date_of_death": str(d.claim_date),
                    "date": str(d.claim_date),
                    "deceased": d.deceased_name,
                    "claimType": d.claim_type,
                    "claimantName": claimant.full_name if claimant else "",
                    "claimantContact": claimant.contact_number if claimant else "",
                    "benefit": str(d.benefit_amount),
                    "dateOfDeath": str(d.claim_date),
                    "member": {
                        "member_id": member.member_id_PK if member else None,
                        "member_name": member.full_name if member else "",
                        "employee_id": member.employee_id or "" if member else "",
                        "department": member.department or "" if member else "",
                        "position": member.position or "" if member else "",
                    },
                }
            )

    return JsonResponse({"ok": True, "aids": items})


@require_POST
@transaction.atomic
def auditor_verify_payment(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    target_id = (request.POST.get("pAuditID") or "").strip()
    remarks = (request.POST.get("pAuditRemarks") or "").strip()
    field_remarks = (request.POST.get("pAuditFieldRemarks") or "").strip()
    result = (request.POST.get("pAuditResult") or "").strip()  # 'Verified' or 'Returned'

    if field_remarks:
        if remarks:
            remarks = remarks + "\n\n" + field_remarks
        else:
            remarks = field_remarks

    if not target_id:
        return JsonResponse({"ok": False, "error": "Missing pAuditID."}, status=400)

    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid pAuditResult."}, status=400)

    entity_type = None
    entity = None
    related_module = None

    # Determine whether it is a MembershipFee or MonthlyDues by probing
    try:
        as_int = int(target_id)
    except ValueError:
        as_int = None

    fee = None
    dues = None
    if as_int is not None:
        fee = MembershipFee.objects.filter(fee_id_PK=as_int).first()
        dues = MonthlyDues.objects.filter(dues_id_PK=as_int).first()

    if fee is not None:
        entity_type = "MembershipFee"
        entity = fee
        related_module = "MEMBERSHIP_FEE"
        related_record_id = fee.fee_id_PK
    elif dues is not None:
        entity_type = "MonthlyDues"
        entity = dues
        related_module = "MONTHLY_DUES"
        related_record_id = dues.dues_id_PK
    else:
        return JsonResponse({"ok": False, "error": "Payment record not found."}, status=404)

    audit_result_text = "Auditor Verified" if result == "Verified" else "Returned for Revision"
    verification_now = timezone.now()

    # Idempotency/Concurrency guard (atomic + write-lock)
    # Lock the TransactionVerification row so concurrent double-clicks
    # can’t both insert RevisionLog/AuditLog/archives.
    tv_table = "medical_aid" if entity_type == "MedicalAid" else "death_aid"
    tv_qs = TransactionVerification.objects.select_for_update().filter(
        table_name=tv_table,
        record_id=related_record_id,
    )
    tv = tv_qs.first()
    if tv is not None and str(tv.verification_status) == "Returned for Revision":
        return JsonResponse({"ok": True})

    # ---- Idempotency/Concurrency guard (atomic + write-lock) ----
    # Lock the TransactionVerification row so concurrent double-clicks
    # can’t both insert RevisionLog/AuditLog/archives.
    tv_table = "membership_fee" if isinstance(entity, MembershipFee) else "monthly_dues"
    tv_qs = TransactionVerification.objects.select_for_update().filter(
        table_name=tv_table,
        record_id=related_record_id,
    )
    tv = tv_qs.first()

    if tv is not None and str(tv.verification_status) == "Returned for Revision":
        # Already returned (duplicate submit). Idempotently succeed.
        return JsonResponse({"ok": True})

    uploaded = request.FILES.get("p_findings_file")

    # Write to AuditorPaymentVerification (new table) instead of FINANCIAL_DOCUMENT_ARCHIVE.
    evidence_file_path = ""
    evidence_file_hash = ""

    if uploaded and getattr(uploaded, "size", 0) > 0:
        filename = uploaded.name
        evidence_file_path = default_storage.save(
            f"auditor_payment_evidence/{timezone.now().strftime('%Y%m%d')}_{filename}",
            uploaded,
        )

        # Best-effort hash (don't fail if hashing fails)
        try:
            hasher = hashlib.sha256()
            data = uploaded.read()
            hasher.update(data)
            evidence_file_hash = hasher.hexdigest()
        except Exception:
            evidence_file_hash = ""

    target_table = "membership_fee" if isinstance(entity, MembershipFee) else "monthly_dues"

    AuditorPaymentVerification.objects.update_or_create(
        target_table=target_table,
        target_record_id=related_record_id,
        defaults={
            "auditor_id_FK": officer,
            "verified_at": verification_now,
            "result_status": audit_result_text,
            "auditor_remarks": remarks or "",
            "evidence_file_path": evidence_file_path,
            "evidence_file_hash": evidence_file_hash,
        },
    )


    if isinstance(entity, MembershipFee):
        tv_table = "membership_fee"
    else:
        entity.payment_status = audit_result_text
        entity.save(update_fields=["payment_status"])
        tv_table = "monthly_dues"

    # Update transaction_verification record
    TransactionVerification.objects.filter(
        table_name=tv_table,
        record_id=related_record_id
    ).update(
        verification_status=audit_result_text,
        auditor_id_FK=officer,
        verified_at=verification_now
    )

    # NEW: write revision_log when auditor returns for correction
    if result == "Returned":
        snapshot = _serialize_record(entity)
        RevisionLog.objects.create(
            content_type=ContentType.objects.get_for_model(entity),
            object_id=entity.pk,
            rejection_reason=remarks or "",
            snapshot_data=snapshot,
            auditor_id_FK=officer,
        )

    action = "Audit Verified" if result == "Verified" else "Audit Returned"

    AuditLog.objects.create(
        actor_type="Auditor",
        actor_id=officer.user_id_PK,
        action=action,
        entity_type=entity_type,
        # For payments, keep AUDIT_LOG integrity by storing a FinancialDocumentArchive FK.
        # If no archive row was created in this flow, fallback to a placeholder creation.
        entity_id=FinancialDocumentArchive.objects.create(
            related_module=related_module,
            related_record_id=related_record_id,
            document_type="auditor_finding",
            file_path="",
            file_hash="",
            verification_status=audit_result_text,
            uploaded_by_user_id_FK=officer,
        ),

        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        device_info="",
    )

    # NOTE: Do not write payment remarks/evidence to legacy AUDIT_FINDINGS_REPORT
    # (President display for payments now reads from AuditorPaymentVerification).


    return JsonResponse({"ok": True})


@require_POST
@transaction.atomic
def auditor_verify_aid(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    target_id = (request.POST.get("aAuditID") or "").strip()
    remarks = (request.POST.get("aAuditRemarks") or "").strip()
    result = (request.POST.get("aAuditResult") or "").strip()

    if not target_id:
        return JsonResponse({"ok": False, "error": "Missing aAuditID."}, status=400)

    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid aAuditResult."}, status=400)

    table_hint = None
    raw_id = target_id
    if "-" in target_id:
        parts = target_id.split("-", 1)
        table_hint = parts[0]
        raw_id = parts[1]

    try:
        as_int = int(raw_id)
    except (ValueError, TypeError):
        as_int = None

    med = None
    dth = None
    if as_int is not None:
        if table_hint == "medical":
            med = MedicalAid.objects.filter(medical_aid_id_PK=as_int).first()
        elif table_hint == "death":
            dth = DeathAid.objects.filter(death_aid_id_PK=as_int).first()
        else:
            med = MedicalAid.objects.filter(medical_aid_id_PK=as_int).first()
            dth = DeathAid.objects.filter(death_aid_id_PK=as_int).first()

    entity = None
    if med is not None:
        entity_type = "MedicalAid"
        related_module = "MEDICAL_AID"
        related_record_id = med.medical_aid_id_PK
        audit_result_text = "Auditor Verified" if result == "Verified" else "Returned for Revision"
        entity = med
        med.status = audit_result_text
        med.auditor_verified_by_user_id_FK = officer
        med.save(update_fields=["status", "auditor_verified_by_user_id_FK"])

    elif dth is not None:
        entity_type = "DeathAid"
        related_module = "DEATH_AID"
        related_record_id = dth.death_aid_id_PK
        audit_result_text = "Auditor Verified" if result == "Verified" else "Returned for Revision"
        entity = dth
        dth.status = audit_result_text
        dth.auditor_verified_by_user_id_FK = officer
        dth.save(update_fields=["status", "auditor_verified_by_user_id_FK"])

    else:
        return JsonResponse({"ok": False, "error": "Aid record not found."}, status=404)

    # NEW: write revision_log when auditor returns for correction
    if result == "Returned":
        snapshot = _serialize_record(entity)
        RevisionLog.objects.create(
            content_type=ContentType.objects.get_for_model(entity),
            object_id=entity.pk,
            rejection_reason=remarks or "",
            snapshot_data=snapshot,
            auditor_id_FK=officer,
        )

    uploaded = request.FILES.get("a_findings_file")

    # Store evidence/remarks in the new single-table AuditorAidVerification
    evidence_file_path = ""
    evidence_file_hash = ""

    if uploaded and getattr(uploaded, "size", 0) > 0:
        filename = uploaded.name
        evidence_file_path = default_storage.save(
            f"auditor_aid_evidence/{timezone.now().strftime('%Y%m%d')}_{filename}",
            uploaded,
        )

        try:
            hasher = hashlib.sha256()
            data = uploaded.read()
            hasher.update(data)
            evidence_file_hash = hasher.hexdigest()
        except Exception:
            evidence_file_hash = ""

    target_table = "medical_aid" if entity_type == "MedicalAid" else "death_aid"

    # Idempotent: unique by (target_table, target_record_id)
    AuditorAidVerification.objects.update_or_create(
        target_table=target_table,
        target_record_id=related_record_id,
        defaults={
            "auditor_id_FK": officer,
            "verified_at": timezone.now(),
            "result_status": audit_result_text,
            "auditor_remarks": remarks or "",
            "evidence_file_path": evidence_file_path,
            "evidence_file_hash": evidence_file_hash,
        },
    )

    # Keep existing legacy FINANCIAL_DOCUMENT_ARCHIVE flow for AuditLog FK integrity.
    if uploaded and getattr(uploaded, "size", 0) > 0:
        archive = _file_upload_to_archive(
            request=request,
            related_module=related_module,
            related_record_id=related_record_id,
            document_type="auditor_finding",
            uploaded_file=uploaded,
            verification_status=audit_result_text,
        )
    else:
        archive = _create_placeholder_archive(
            request=request,
            related_module=related_module,
            related_record_id=related_record_id,
            document_type="auditor_finding",
            verification_status=audit_result_text,
        )


    action = "Audit Verified" if result == "Verified" else "Audit Returned"

    AuditLog.objects.create(
        actor_type="Auditor",
        actor_id=officer.user_id_PK,
        action=action,
        entity_type=entity_type,
        entity_id=archive,
        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        device_info="",
    )

    return JsonResponse({"ok": True})


@require_GET
def auditor_pending_membership_fees(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    # Get all fees and check their audit status via TransactionVerification
    all_fees = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").all()
    items: List[Dict[str, Any]] = []

    for f in all_fees:
        # Check if there's a pending TransactionVerification for this fee
        verification_status = TransactionVerification.objects.filter(
            table_name="membership_fee",
            record_id=f.fee_id_PK,
        ).values_list("verification_status", flat=True).first()

        # Include if no verification exists or if status is "Pending"
        if verification_status is None or verification_status == "Pending":
            member = f.member_id_FK
            encoder_name = ""
            if f.recorded_by_user_id_FK:
                encoder_name = getattr(f.recorded_by_user_id_FK, "full_name", "") or str(f.recorded_by_user_id_FK.user_id_PK)

            items.append({
                "fee_id": f.fee_id_PK,
                "ref": f.receipt_number or "",
                "member_id": member.member_id_PK if member else None,
                "member_name": member.full_name if member else "",
                "amount": str(f.amount),
                "month_covered": f.month_covered or "",
                "payment_date": str(f.payment_date),
                "payment_status": f.payment_status,
                "deposit_reference": f.deposit_reference or "",
                "encoded_by": encoder_name,
            })

    items.sort(key=lambda x: x["fee_id"], reverse=True)
    return JsonResponse({"ok": True, "fees": items})


@require_POST
@transaction.atomic
def auditor_verify_membership_fee(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    target_id = (request.POST.get("mfAuditID") or "").strip()
    remarks = (request.POST.get("mfAuditRemarks") or "").strip()
    field_remarks = (request.POST.get("mfAuditFieldRemarks") or "").strip()
    result = (request.POST.get("mfAuditResult") or "").strip()

    if field_remarks:
        if remarks:
            remarks = remarks + "\n\n" + field_remarks
        else:
            remarks = field_remarks

    if not target_id:
        return JsonResponse({"ok": False, "error": "Missing mfAuditID."}, status=400)

    try:
        fee = MembershipFee.objects.get(fee_id_PK=int(target_id))
    except MembershipFee.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Membership fee not found."}, status=404)

    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid mfAuditResult."}, status=400)

    audit_result_text = "Auditor Verified" if result == "Verified" else "Returned for Revision"
    verification_now = timezone.now()

    # Idempotency/concurrency guard: lock the verification row so double-clicking
    # doesn't create duplicate AuditLog/archives.
    tv_qs = TransactionVerification.objects.select_for_update().filter(
        table_name="membership_fee",
        record_id=fee.fee_id_PK,
    )
    tv = tv_qs.first()
    if tv is not None and str(tv.verification_status) != "Pending":
        # Already processed by a previous click in this or another concurrent request.
        return JsonResponse({"ok": True})

    Uploaded = request.FILES.get("p_findings_file")
    if Uploaded and getattr(Uploaded, "size", 0) > 0:
        _file_upload_to_archive(
            request=request,
            related_module="MEMBERSHIP_FEE",
            related_record_id=fee.fee_id_PK,
            document_type="auditor_finding",
            uploaded_file=Uploaded,
            verification_status=audit_result_text,
        )
    else:
        _create_placeholder_archive(
            request=request,
            related_module="MEMBERSHIP_FEE",
            related_record_id=fee.fee_id_PK,
            document_type="auditor_finding",
            verification_status=audit_result_text,
        )

    # Ensure TransactionVerification exists (some records may not have a row yet)
    if tv is None:
        TransactionVerification.objects.create(
            table_name="membership_fee",
            record_id=fee.fee_id_PK,
            verification_status=audit_result_text,
            auditor_id_FK=officer,
            verified_at=verification_now,
        )
    else:
        tv.verification_status = audit_result_text
        tv.auditor_id_FK = officer
        tv.verified_at = verification_now
        tv.save(update_fields=["verification_status", "auditor_id_FK", "verified_at"])

    AuditLog.objects.create(
        actor_type="Auditor",
        actor_id=officer.user_id_PK,
        action="Audit Verified" if result == "Verified" else "Audit Returned",
        entity_type="MembershipFee",
        entity_id=fee.fee_id_PK,
        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        device_info="",
    )

    return JsonResponse({"ok": True})



@require_POST
@transaction.atomic
def reject_transaction(request: HttpRequest):

    """Flow A: Auditor rejects a financial record for revision.

    Bug B: must be idempotent to prevent duplicate logs when the user double-submits.
    We short-circuit if transaction_verification is already in "Returned for Revision".
    """

    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    table_name = (request.POST.get("table_name") or "").strip()
    record_id = (request.POST.get("record_id") or "").strip()
    rejection_reason = (request.POST.get("rejection_reason") or "").strip()

    if table_name not in MODEL_MAP:
        return JsonResponse({"ok": False, "error": "Invalid table_name."}, status=400)
    if not record_id:
        return JsonResponse({"ok": False, "error": "Missing record_id."}, status=400)

    Model = MODEL_MAP[table_name]
    try:
        record = Model.objects.get(pk=int(record_id))
    except (ValueError, Model.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Record not found."}, status=404)

    # Idempotency / duplicate protection:
    # Lock the verification row (create-or-lock path) so concurrent double-clicks can’t
    # both create logs at the same time.
    tv_qs = TransactionVerification.objects.select_for_update().filter(
        table_name=table_name,
        record_id=int(record_id),
    )

    tv = tv_qs.first()
    if tv is not None and str(tv.verification_status) == "Returned for Revision":
        # Already rejected (duplicate submit). Idempotently succeed.
        return JsonResponse({"ok": True}, status=200)



    snapshot = _serialize_record(record)


    if tv is None:
        TransactionVerification.objects.create(
            table_name=table_name,
            record_id=int(record_id),
            verification_status="Returned for Revision",
            auditor_id_FK=officer,
        )
    else:
        tv.verification_status = "Returned for Revision"
        tv.auditor_id_FK = officer
        tv.save(update_fields=["verification_status", "auditor_id_FK"])

    RevisionLog.objects.create(
        content_type=ContentType.objects.get_for_model(Model),
        object_id=record.pk,
        rejection_reason=rejection_reason,
        snapshot_data=snapshot,
        auditor_id_FK=officer,
    )

    archive = _create_placeholder_archive(
        request=request,
        related_module=table_name.upper(),
        related_record_id=int(record_id),
        document_type="rejection",
        verification_status="Returned for Revision",
    )

    AuditLog.objects.create(
        actor_type="Auditor",
        actor_id=officer.user_id_PK,
        action="Transaction Rejected",
        entity_type=table_name,
        entity_id=archive,
        ip_address=request.META.get("REMOTE_ADDR", "0.0.0.0"),
    )

    return JsonResponse({"ok": True})



@require_GET
def auditor_supporting_proof(request: HttpRequest, model_type: str, record_id: int):
    """Fetch supporting proof media for a given financial record."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    if model_type not in MODEL_MAP:
        return JsonResponse({"ok": False, "error": "Invalid model type."}, status=400)

    Model = MODEL_MAP[model_type]
    try:
        record = Model.objects.get(pk=record_id)
    except (ValueError, Model.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Record not found."}, status=404)

    content_type = ContentType.objects.get_for_model(record)
    proof = SupportingProof.objects.filter(
        content_type=content_type,
        object_id=record.pk
    ).first()

    if not proof:
        return JsonResponse({"ok": True, "proof": None})

    file_url = proof.file.url if proof.file else None

    return JsonResponse({
        "ok": True,
        "proof": {
            "file_url": file_url,
            "file_type": proof.file_type,
            "file_name": proof.file_name
        }
    })
