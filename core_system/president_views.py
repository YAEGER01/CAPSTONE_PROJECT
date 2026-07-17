import hashlib
import json
import logging
import secrets
import threading
from datetime import datetime
from typing import Any, Dict, List

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Sum
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

from core_system.guards import check_zero_trust, require_role
from core_system.models import (
    AidTrackingPost,
    BylawsFile,
    Department,
    Contribution,
    DeathAid,
    FinancialDocumentArchive,
    FundTransaction,
    GlobalAuditTrail,
    MedicalAid,
    Member,
    MembershipFee,
    MonthlyDues,
    OfficerUser,
    PayrollBatch,
    PayrollDeduction,
    SystemSetting,
    TransactionArchive,
    TransactionVerification,
)
from core_system.constants.status_constants import Status, can_president_act, is_approved, is_rejected
from core_system.constants.policy_constants import (
    get_death_aid_amount,
    get_membership_fee_amount,
    get_monthly_dues_amount,
    get_contribution_amount_for_aid,
    is_exempt_from_dues_and_aid,
    POLICY,
    _get_setting_override,
)
from core_system.shared_view_utils import (
    MODEL_MAP,
    _audit_evidence_filename,
    _get_auditor_verification,
    _record_audit_trail,
    _record_bulk_audit_trail,
    _log_sensitive_read,
    _payment_item_to_json,
    archive_transaction,
    _broadcast_pending_counts,
    _broadcast_to_group,
    resolve_officer_from_session,
)
from core_system.services.compliance import (
    dues_compliance_summary,
    active_members_qs,
)
from core_system.services.email_service import (
    queue_aid_emails,
    process_email_queue,
)
from core_system.auth_utils import sha256_hex


def permission_denied_view(request, exception=None):
    return render(request, "errors/403.html", status=403)


@require_GET
def audit_trail_api(request: HttpRequest, table_name: str, record_id: int):
    allowed_roles = {"Treasurer", "Auditor", "President"}
    stored_role = (request.session.get("role") or "").strip()
    if stored_role not in allowed_roles:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Forbidden for this role.")

    entries = GlobalAuditTrail.objects.filter(
        table_name=table_name,
        record_id=int(record_id),
    ).order_by("-timestamp")

    limit = int(request.GET.get("limit", 200))
    offset = int(request.GET.get("offset", 0))
    if limit > 200:
        limit = 200
    total = entries.count()
    entries = entries[offset : offset + limit]

    rows = []
    for entry in entries:
        rows.append(
            {
                "trail_id": entry.trail_id,
                "action": entry.action,
                "actor_type": entry.actor_type,
                "actor_id": entry.actor_id,
                "actor_name": entry.actor_name,
                "old_values": entry.old_values,
                "new_values": entry.new_values,
                "notes": entry.notes,
                "ip_address": str(entry.ip_address) if entry.ip_address else None,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "table_name": table_name,
            "record_id": record_id,
            "total": total,
            "entries": rows,
        }
    )


# ==========================================================================
# PRESIDENT WORKSPACE VIEWS
# ==========================================================================

def president_dashboard(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer_full_name = ""
    officer_role = "President"

    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "access_token": request.session.get("access_token", ""),
        "departments": Department.objects.filter(is_active=True).order_by("name"),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    return render(request, "website/President/president_dashboard.html", context)


def _load_pending_dues_record(v):
    """Load monthly dues record data for presidential queue."""
    payment_record = (
        MonthlyDues.objects.filter(dues_id_PK=v.record_id)
        .select_related("member_id_FK", "recorded_by_user_id_FK")
        .first()
    )
    if not payment_record:
        return None, None, None

    p_member = payment_record.member_id_FK
    member_data = {
        "member_name": p_member.full_name,
        "employee_id": p_member.employee_id,
        "department": p_member.department,
        "membership_status": p_member.membership_status,
        "contact_info": p_member.contact_number,
    }
    method = (payment_record.payment_method or "").strip().lower()
    is_salary = method == "salary deduction"

    payment_details = {
        "reference_code": payment_record.receipt_number
        or payment_record.deduction_batch_reference
        or "—",
        "covered_period": payment_record.month_covered,
        "amount_paid": float(payment_record.amount),
        "expected": get_monthly_dues_amount(),
        "payment_method": payment_record.payment_method,
        "encoder_name": (
            payment_record.recorded_by_user_id_FK.full_name
            if payment_record.recorded_by_user_id_FK
            else "System"
        ),
        "type": "monthly_dues_salary" if is_salary else "monthly_dues_otc",
    }

    if is_salary:
        approved_fields = {
            "membership_type": "Monthly Dues (Salary Deduction)",
            "membership_ref": payment_record.remittance_reference or payment_record.receipt_number or "",
            "membership_month": payment_record.month_covered or "",
            "membership_amount": float(payment_record.amount),
            "otc_month": "—", "otc_amount": 0, "otc_ref": "—",
            "salary_month": payment_record.month_covered,
            "salary_amount": float(payment_record.amount),
            "salary_ref": payment_record.remittance_reference or payment_record.receipt_number or "",
        }
    else:
        approved_fields = {
            "membership_type": "Monthly Dues (OTC)",
            "membership_ref": payment_record.receipt_number or "",
            "membership_month": payment_record.month_covered or "",
            "membership_amount": float(payment_record.amount),
            "salary_month": "—", "salary_amount": 0, "salary_ref": "—",
            "otc_month": payment_record.month_covered,
            "otc_amount": float(payment_record.amount),
            "otc_ref": payment_record.receipt_number or "",
        }

    return member_data, payment_details, approved_fields


def _load_pending_fee_record(v):
    """Load membership fee record data for presidential queue."""
    payment_record = (
        MembershipFee.objects.filter(fee_id_PK=v.record_id)
        .select_related("member_id_FK", "recorded_by_user_id_FK")
        .first()
    )
    if not payment_record:
        return None, None, None

    p_member = payment_record.member_id_FK
    member_data = {
        "member_name": p_member.full_name,
        "employee_id": p_member.employee_id,
        "department": p_member.department,
        "membership_status": p_member.membership_status,
        "contact_info": p_member.contact_number,
    }
    payment_details = {
        "reference_code": payment_record.receipt_number
        or payment_record.deposit_reference
        or "—",
        "covered_period": "One-Time Fee",
        "amount_paid": float(payment_record.amount),
        "expected": get_membership_fee_amount(),
        "payment_method": payment_record.payment_method,
        "encoder_name": (
            payment_record.recorded_by_user_id_FK.full_name
            if payment_record.recorded_by_user_id_FK
            else "System"
        ),
        "type": "membership_fee",
    }
    approved_fields = {
        "membership_type": "OTC Membership Fee",
        "membership_ref": payment_record.receipt_number or payment_record.deposit_reference or "",
        "membership_month": "One-Time Fee",
        "membership_amount": float(payment_record.amount),
        "otc_month": "—", "otc_amount": 0, "otc_ref": "—",
        "salary_month": "—", "salary_amount": 0, "salary_ref": "—",
    }

    return member_data, payment_details, approved_fields


def _build_auditor_info(v):
    """Build auditor verification info for presidential queue item."""
    apv = _get_auditor_verification(str(v.table_name).lower(), v.record_id)
    if apv:
        return {
            "auditorName": apv.auditor_id_FK.full_name if apv.auditor_id_FK_id else "—",
            "auditorDate": (
                apv.verified_at.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(apv, "verified_at", None)
                else (v.verified_at.strftime("%Y-%m-%d %H:%M:%S") if v.verified_at else "—")
            ),
            "auditorEvidence": _audit_evidence_filename(apv.evidence_file_path) if apv.evidence_file_path else "—",
            "auditorRemarks": (
                apv.auditor_remarks.strip()
                if apv.auditor_remarks and str(apv.auditor_remarks).strip()
                else "—"
            ),
        }
    return {
        "auditorName": v.auditor_id_FK.full_name if v.auditor_id_FK_id else "—",
        "auditorDate": v.verified_at.strftime("%Y-%m-%d %H:%M:%S") if v.verified_at else "—",
        "auditorEvidence": "—",
        "auditorRemarks": "—",
    }


@require_GET
def get_pending_presidential_payments(request):
    verifications = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related("auditor_id_FK")

    data = []
    for v in verifications:
        tn = str(v.table_name).lower()

        if tn == "monthly_dues":
            member_data, payment_details, approved_fields = _load_pending_dues_record(v)
        else:
            member_data, payment_details, approved_fields = _load_pending_fee_record(v)

        if not member_data:
            continue

        logs = GlobalAuditTrail.objects.filter(
            table_name=v.table_name,
            record_id=v.record_id,
            action__in=["VERIFIED", "RETURNED", "CORRECTION_REQUIRED", "REJECTED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline_data = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in logs
        ]

        auditor_info = _build_auditor_info(v)

        record_payload = {
            "id": v.verification_id,
            **auditor_info,
            "timeline": timeline_data,
            "returned_reason": v.returned_reason or "",
            "return_count": v.return_count or 0,
        }
        record_payload.update(member_data)
        record_payload.update(payment_details)
        record_payload.update(approved_fields)

        data.append(record_payload)

    return JsonResponse({"success": True, "payments": data}, safe=False)


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
def _build_treasurer_original(record):
    if record is None:
        return {"member": None}
    if isinstance(record, MembershipFee):
        ref = record.receipt_number or ""
    else:
        ref = record.receipt_number or record.remittance_reference or ""
    return {
        "memberName": record.member_id_FK.full_name,
        "employeeId": record.member_id_FK.employee_id or "",
        "department": record.member_id_FK.department or "",
        "status": record.member_id_FK.membership_status or "",
        "contact": record.member_id_FK.contact_number or "",
        "covered": record.month_covered or "",
        "expected": str(record.amount),
        "method": record.payment_method or "",
        "ref": ref,
        "encoder": getattr(record.recorded_by_user_id_FK, "full_name", "") or "",
    }


def president_auditor_approved_payment_detail(request: HttpRequest, entity_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

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

    approved_membership = _payment_item_to_json("membership_fee", fee) if fee else None
    approved_otc_dues = None
    approved_salary_dues = None
    if dues:
        method = (dues.payment_method or "").lower()
        if method == "salary deduction":
            approved_salary_dues = _payment_item_to_json("monthly_dues", dues)
        else:
            approved_otc_dues = _payment_item_to_json("monthly_dues", dues)

    auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else ""
    auditor_date = (tv.verified_at.isoformat() if tv.verified_at else "")

    evidence_filename = ""
    archive = FinancialDocumentArchive.objects.filter(
        related_record_id=entity_id,
        document_type="auditor_finding",
        related_module=tv.table_name.upper(),
    ).order_by("-uploaded_at").first()
    if archive and archive.file_path:
        evidence_filename = archive.file_path.split("/")[-1]

    return JsonResponse({
        "ok": True,
        "item": {
            "id": str(entity_id),
            "table_name": tv.table_name,
            "auditorName": auditor_name,
            "auditorDate": auditor_date,
            "auditorEvidence": evidence_filename or "",
            "auditorRemarks": "—",
            "returned_reason": tv.returned_reason or "",
            "return_count": tv.return_count or 0,
        },
        "approvedMembership": approved_membership,
        "approvedOtcDues": approved_otc_dues,
        "approvedSalaryDues": approved_salary_dues,
        "treasurerOriginal": _build_treasurer_original(fee or dues),
        "timeline": [],
    })


@require_GET
def president_pending_contributions(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    verifications = TransactionVerification.objects.filter(
        table_name="contribution",
        target_category="aid_contribution",
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related("auditor_id_FK").order_by("verification_id")

    items = []
    for v in verifications:
        contrib = Contribution.objects.filter(
            contribution_id_PK=v.record_id
        ).select_related("member_id_FK", "aid_tracking_post_id_FK").first()
        if not contrib:
            continue

        member = contrib.member_id_FK
        post = contrib.aid_tracking_post_id_FK
        member_name = member.full_name if member else "Unknown"

        logs = GlobalAuditTrail.objects.filter(
            table_name="contribution",
            record_id=v.record_id,
            action__in=["VERIFIED", "RETURNED", "CORRECTION_REQUIRED", "REJECTED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in logs
        ]

        aid_type_label = post.aid_type if post else "—"
        source_type_label = {
            "medical_aid": "Medical Aid",
            "death_aid": "Death Aid",
        }.get(post.source_type if post else "", "—")

        items.append({
            "verification_id": v.verification_id,
            "record_id": contrib.contribution_id_PK,
            "member_name": member_name,
            "member_id": member.member_id_PK if member else None,
            "expected_amount": float(contrib.expected_amount),
            "paid_amount": float(contrib.paid_amount),
            "payment_date": str(contrib.payment_date) if contrib.payment_date else "—",
            "status": contrib.status,
            "aid_type": aid_type_label,
            "source_type": source_type_label,
            "post_id": post.post_id_PK if post else None,
            "auditor_name": v.auditor_id_FK.full_name if v.auditor_id_FK_id else "—",
            "auditor_remarks": v.auditor_remarks or "",
            "verified_at": v.verified_at.strftime("%Y-%m-%d %H:%M:%S") if v.verified_at else "—",
            "returned_reason": v.returned_reason or "",
            "return_count": v.return_count or 0,
            "timeline": timeline,
        })

    return JsonResponse({"success": True, "contributions": items}, safe=False)


@require_http_methods(["POST"])
def submit_presidential_contribution_decision(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard
    try:
        body = json.loads(request.body)
        target_id = body.get("target_id")
        decision = body.get("decision")
        remarks = body.get("remarks", "")

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({"success": False, "message": "Officer session missing."}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))
        verification = get_object_or_404(TransactionVerification, verification_id=target_id)

        if not can_president_act(verification.verification_status):
            return JsonResponse({"success": False, "message": "Transaction is not in a state that can be acted upon by the President."}, status=400)

        if decision == "Approved":
            verification.verification_status = "Approved"
            verification.approved_at = timezone.now()
            action_str = "Presidential Executive Approval Completed"
        elif decision == "Rejected":
            verification.verification_status = "Rejected"
            if not remarks:
                return JsonResponse({"success": False, "message": "Remarks are mandatory for rejections."}, status=400)
            action_str = "Flagged Deficient by Executive Order"
        else:
            return JsonResponse({"success": False, "message": "Invalid decision route."}, status=400)

        verification.president_id_FK = officer
        verification.save()

        if verification.verification_status == "Approved":
            archive = archive_transaction(verification.table_name, verification.record_id, officer)
            if archive:
                FundTransaction.objects.create(
                    direction="inflow",
                    amount=archive.amount,
                    source_type="aid_contribution",
                    source_id=verification.record_id,
                    description=f"Aid contribution — {archive.member_name}",
                    recorded_by_user_id_FK=officer,
                )

        _record_audit_trail(
            table=verification.table_name,
            record_id=verification.record_id,
            action="APPROVED" if verification.verification_status == "Approved" else "REJECTED",
            actor=officer,
            notes=remarks or None,
            ip=request.META.get("REMOTE_ADDR"),
        )

        _broadcast_pending_counts()
        return JsonResponse({"success": True, "message": f"Contribution verification {verification.verification_status}."})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_GET
def president_auditor_approved_aids_queue(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    medicals = MedicalAid.objects.select_related(
        "member_id_FK",
        "auditor_verified_by_user_id_FK",
        "treasurer_validated_by_user_id_FK",
    ).filter(
        status="Auditor Verified",
        president_decided_by_user_id_FK__isnull=True,
    ).order_by("-medical_aid_id_PK")

    deaths = DeathAid.objects.select_related(
        "member_id_FK",
        "claimant_id_FK",
        "treasurer_validated_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
    ).filter(
        status="Auditor Verified",
        president_decided_by_user_id_FK__isnull=True,
    ).order_by("-death_aid_id_PK")

    items: List[Dict[str, Any]] = []
    pres_med_record_ids = []

    for m in medicals:
        pres_med_record_ids.append(m.medical_aid_id_PK)
        member = m.member_id_FK
        tv = TransactionVerification.objects.filter(
            table_name="medical_aid",
            record_id=m.medical_aid_id_PK,
        ).order_by("-verified_at").first()

        auditor_name = "—"
        auditor_date = "—"
        auditor_evidence = "—"
        auditor_remarks = "—"
        if tv:
            auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else "—"
            auditor_date = tv.verified_at.strftime("%Y-%m-%d %H:%M:%S") if tv.verified_at else "—"
            auditor_evidence = tv.evidence_file_path.split("/")[-1] if tv.evidence_file_path else "—"
            auditor_remarks = (tv.auditor_remarks or "").strip() or "—"

        audit_logs = GlobalAuditTrail.objects.filter(
            table_name="medical_aid",
            record_id=m.medical_aid_id_PK,
        ).filter(
            action__in=["VERIFIED", "RETURNED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in audit_logs
        ]

        if not timeline and tv:
            timeline = [{"timestamp": auditor_date, "role": "Auditor", "user": auditor_name, "action": "Verified", "notes": auditor_remarks, "old_values": None, "new_values": None}]

        req_amount = float(m.validated_aid_amount or m.requested_amount or 0)
        bill_amount = float(m.hospital_bill_amount or 0)
        member_name = member.full_name if member else ""

        items.append(
            {
                "id": "medical-" + str(m.medical_aid_id_PK),
                "entity_id": int(m.medical_aid_id_PK),
                "aid_type": "medical_aid",
                "type": "Medical Aid Request",
                "request_date": str(m.request_date),
                "medical_case": m.document_status or m.policy_record_status or "",
                "requested_amount": req_amount,
                "hospital": m.hospital_name or member_name,
                "hospital_date": str(m.hospital_date) if m.hospital_date else "",
                "total_hospital_bill": bill_amount,
                "validated_aid_amount": float(m.validated_aid_amount or 0),
                "treasurer_validation": m.document_status or m.policy_record_status or "",
                "date": str(m.request_date),
                "reqAmount": req_amount,
                "bill": bill_amount,
                "reason": m.document_status or m.policy_record_status or "",
                "validation": m.document_status or m.policy_record_status or "",
                "memberName": member_name,
                "member": {
                    "member_id": member.member_id_PK if member else None,
                    "member_name": member_name,
                    "employee_id": member.employee_id or "" if member else "",
                    "department": member.department or "" if member else "",
                    "position": member.position or "" if member else "",
                    "contact": getattr(member, "contact_number", None) or "" if member else "",
                    "email": getattr(member, "email", None) or "" if member else "",
                },
                "auditorName": auditor_name,
                "auditorDate": auditor_date,
                "auditorEvidence": auditor_evidence,
                "auditorRemarks": auditor_remarks,
                "returned_reason": tv.returned_reason if tv else "",
                "return_count": tv.return_count if tv else 0,
                "timeline": timeline,
            }
        )

    for d in deaths:
        member = d.member_id_FK
        claimant = d.claimant_id_FK
        tv = TransactionVerification.objects.filter(
            table_name="death_aid",
            record_id=d.death_aid_id_PK,
        ).order_by("-verified_at").first()

        auditor_name = "—"
        auditor_date = "—"
        auditor_evidence = "—"
        auditor_remarks = "—"
        if tv:
            auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else "—"
            auditor_date = tv.verified_at.strftime("%Y-%m-%d %H:%M:%S") if tv.verified_at else "—"
            auditor_evidence = tv.evidence_file_path.split("/")[-1] if tv.evidence_file_path else "—"
            auditor_remarks = (tv.auditor_remarks or "").strip() or "—"

        audit_logs = GlobalAuditTrail.objects.filter(
            table_name="death_aid",
            record_id=d.death_aid_id_PK,
        ).filter(
            action__in=["VERIFIED", "RETURNED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in audit_logs
        ]

        if not timeline and tv:
            timeline = [{"timestamp": auditor_date, "role": "Auditor", "user": auditor_name, "action": "Verified", "notes": auditor_remarks, "old_values": None, "new_values": None}]

        benefit_amount = float(d.benefit_amount or 0)
        member_name = member.full_name if member else ""

        items.append(
            {
                "id": "death-" + str(d.death_aid_id_PK),
                "entity_id": int(d.death_aid_id_PK),
                "aid_type": "death_aid",
                "type": "Death Aid Claim",
                "claim_date": str(d.claim_date),
                "deceased_name": d.deceased_name,
                "relationship_to_member": d.relationship_to_member,
                "relationshipGroup": d.relationship_group,
                "claim_type": d.claim_type,
                "claimant_name": claimant.full_name if claimant else "",
                "claimant_contact": claimant.contact_number if claimant else "",
                "bill_amount": float(d.bill_amount) if d.bill_amount else 0,
                "benefit_amount": benefit_amount,
                "date_of_death": str(d.claim_date),
                "date": str(d.claim_date),
                "deceased": d.deceased_name,
                "relationship": d.relationship_to_member,
                "relationshipGroup": d.relationship_group,
                "claimType": d.claim_type,
                "claimantName": claimant.full_name if claimant else "",
                "claimantContact": claimant.contact_number if claimant else "",
                "benefit": benefit_amount,
                "dateOfDeath": str(d.claim_date),
                "deathDate": str(d.claim_date),
                "memberName": member_name,
                "member": {
                    "member_id": member.member_id_PK if member else None,
                    "member_name": member_name,
                    "employee_id": member.employee_id or "" if member else "",
                    "department": member.department or "" if member else "",
                    "position": member.position or "" if member else "",
                },
                "auditorName": auditor_name,
                "auditorDate": auditor_date,
                "auditorEvidence": auditor_evidence,
                "auditorRemarks": auditor_remarks,
                "returned_reason": tv.returned_reason if tv else "",
                "return_count": tv.return_count if tv else 0,
                "timeline": timeline,
            }
        )

    if pres_med_record_ids:
        _log_sensitive_read(request, "medical_aid", pres_med_record_ids, "President viewed auditor-approved medical aid queue")

    return JsonResponse({"success": True, "aids": items})


@require_http_methods(["POST"])
def submit_presidential_decision(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard
    try:
        body = json.loads(request.body)
        target_id = body.get("target_id")
        decision = body.get("decision")
        remarks = body.get("remarks", "")

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse(
                {"success": False, "message": "Officer session missing."}, status=401
            )
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))
        verification = get_object_or_404(
            TransactionVerification, verification_id=target_id
        )

        if not can_president_act(verification.verification_status):
            return JsonResponse(
                {"success": False, "message": "Transaction is not in a state that can be acted upon by the President."},
                status=400,
            )

        if decision == "Approved":
            verification.verification_status = "Approved"
            verification.approved_at = timezone.now()
            action_str = "Presidential Executive Approval Completed"
        elif decision == "Rejected":
            verification.verification_status = "Rejected"
            if not remarks:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Remarks are mandatory for rejections.",
                    },
                    status=400,
                )
            action_str = "Flagged Deficient by Executive Order"
        else:
            return JsonResponse(
                {"success": False, "message": "Invalid decision route."}, status=400
            )

        verification.president_id_FK = officer
        verification.save()

        if verification.verification_status == "Approved":
            archive = archive_transaction(
                verification.table_name,
                verification.record_id,
                officer,
            )
            if archive and verification.table_name in ("membership_fee", "monthly_dues"):
                FundTransaction.objects.create(
                    direction="inflow",
                    amount=archive.amount,
                    source_type=verification.table_name,
                    source_id=verification.record_id,
                    description=f"{archive.member_name} ({dict(FundTransaction.SOURCE_TYPES).get(verification.table_name, verification.table_name)})",
                    recorded_by_user_id_FK=officer,
                )

        _record_audit_trail(
            table=verification.table_name,
            record_id=verification.record_id,
            action=(
                "APPROVED"
                if verification.verification_status == "Approved"
                else "REJECTED"
            ),
            actor=officer,
            notes=remarks or None,
            ip=request.META.get("REMOTE_ADDR"),
        )

        _broadcast_pending_counts()
        return JsonResponse(
            {
                "success": True,
                "message": f"Transaction status updated to {verification.verification_status}.",
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_http_methods(["POST"])
@transaction.atomic
def submit_presidential_aid_decision(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard
    try:
        body = json.loads(request.body)
        target_id = (body.get("target_id") or "").strip()
        decision = (body.get("decision") or "").strip()
        approved_amount = body.get("approved_amount")
        remarks = (body.get("remarks") or "").strip()

        if not target_id:
            return JsonResponse(
                {"success": False, "message": "Missing target_id."},
                status=400,
            )

        if decision not in {"Approved", "Rejected"}:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid decision value. Use Approved or Rejected.",
                },
                status=400,
            )

        try:
            approved_amount = float(approved_amount)
        except (TypeError, ValueError):
            return JsonResponse(
                {"success": False, "message": "Approved amount must be a number."},
                status=400,
            )

        if approved_amount <= 0:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Approved amount must be greater than zero.",
                },
                status=400,
            )

        if decision == "Rejected" and not remarks:
            return JsonResponse(
                {"success": False, "message": "Remarks are mandatory for rejections."},
                status=400,
            )

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse(
                {"success": False, "message": "Officer session missing."},
                status=401,
            )
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))

        table_name = None
        record = None

        if target_id.startswith("medical-"):
            record_id = int(target_id.replace("medical-", ""))
            record = get_object_or_404(MedicalAid, medical_aid_id_PK=record_id)
            table_name = "medical_aid"
        elif target_id.startswith("death-"):
            record_id = int(target_id.replace("death-", ""))
            record = get_object_or_404(DeathAid, death_aid_id_PK=record_id)
            table_name = "death_aid"
        else:
            return JsonResponse(
                {"success": False, "message": "Invalid target_id format."},
                status=400,
            )

        if table_name == "medical_aid" and decision == "Approved":
            requested = float(record.requested_amount or 0)
            hospital_bill = float(record.hospital_bill_amount or 0)
            if approved_amount > requested:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Approved amount (₱{approved_amount:,.2f}) cannot exceed the requested amount (₱{requested:,.2f}).",
                    },
                    status=400,
                )
            if approved_amount > hospital_bill:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Approved amount (₱{approved_amount:,.2f}) cannot exceed the hospital bill amount (₱{hospital_bill:,.2f}).",
                    },
                    status=400,
                )

        record.president_decided_by_user_id_FK = officer
        record.president_decision = decision
        record.status = decision
        extra_fields = ["president_decided_by_user_id_FK", "president_decision", "status"]
        if table_name == "medical_aid" and decision == "Approved" and approved_amount:
            record.validated_aid_amount = approved_amount
            extra_fields.append("validated_aid_amount")
        if table_name == "death_aid" and decision == "Approved" and approved_amount:
            record.benefit_amount = approved_amount
            extra_fields.append("benefit_amount")
        record.save(update_fields=extra_fields)

        if decision == "Approved":
            archive = archive_transaction(
                table_name,
                record.pk,
                officer,
            )

            relationship = ""
            if table_name == "death_aid":
                relationship = getattr(record, "relationship_to_member", "")

            per_member_amount = get_contribution_amount_for_aid(table_name, relationship)
            active_members = Member.objects.exclude(
                membership_status__iexact="Retired",
            )
            total_expected = active_members.count() * per_member_amount

            post = AidTrackingPost.objects.create(
                archive_id_FK=archive,
                aid_type=table_name,
                target_month=timezone.now().strftime("%Y-%m"),
                total_expected=total_expected,
                total_collected=0,
                status="tracking",
                source_type=table_name,
                source_id=record.pk,
                created_by_user_id_FK=officer,
            )

            Contribution.objects.bulk_create([
                Contribution(
                    aid_tracking_post_id_FK=post,
                    member_id_FK=member,
                    expected_amount=per_member_amount,
                    paid_amount=0,
                    status="NOT_PAID",
                )
                for member in active_members
            ])

            transaction.on_commit(
                lambda: queue_aid_emails(record, table_name, per_member_amount)
            )
            transaction.on_commit(
                lambda: threading.Thread(target=process_email_queue, kwargs={"batch_size": 5}).start()
            )

        TransactionVerification.objects.filter(
            table_name=table_name,
            record_id=record.pk,
        ).update(
            verification_status=decision,
            president_id_FK=officer,
            approved_at=timezone.now(),
        )

        _record_audit_trail(
            table=table_name,
            record_id=record.pk,
            action="APPROVED" if decision == "Approved" else "REJECTED",
            actor=officer,
            new={
                "president_decision": decision,
                "approved_amount": approved_amount,
                "action": f"Presidential {decision}",
            },
            notes=remarks or (f"Presidential {decision}" if decision == "Rejected" else None),
            ip=request.META.get("REMOTE_ADDR"),
        )

        transaction.on_commit(lambda: _broadcast_to_group(
            "treasurer_dashboard", {"type": "data_changed", "section": "aids"}
        ))
        transaction.on_commit(_broadcast_pending_counts)
        if decision == "Approved":
            payload = {
                "type": "aid_post_created",
                "post_id": post.post_id_PK,
                "member_name": record.member_id_FK.full_name
                if hasattr(record, "member_id_FK") and record.member_id_FK
                else "",
                "aid_type": table_name,
                "total_expected": float(total_expected),
                "target_month": post.target_month,
            }
            transaction.on_commit(lambda: async_to_sync(get_channel_layer().group_send)("auditor_dashboard", payload))
            transaction.on_commit(lambda: async_to_sync(get_channel_layer().group_send)("treasurer_dashboard", payload))

        return JsonResponse(
            {
                "success": True,
                "message": f"Aid request {decision.lower()} recorded successfully.",
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_POST
@transaction.atomic
def submit_presidential_decision_batch(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard
    try:
        body = json.loads(request.body)
        ids = body.get("ids", [])
        decision = (body.get("decision") or "").strip()
        remarks = (body.get("remarks") or "").strip()

        if not ids or not isinstance(ids, list):
            return JsonResponse({"success": False, "message": "ids must be a non-empty array."}, status=400)
        if decision not in {"Approved", "Rejected"}:
            return JsonResponse({"success": False, "message": "Invalid decision. Use Approved or Rejected."}, status=400)
        if decision == "Rejected" and not remarks:
            return JsonResponse({"success": False, "message": "Remarks are mandatory for rejections."}, status=400)

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({"success": False, "message": "Officer session missing."}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))

        verifications = TransactionVerification.objects.select_for_update().filter(
            verification_id__in=ids,
        )
        existing_map = {v.verification_id: v for v in verifications}

        processed = 0
        skipped = 0
        audit_entries = []
        fund_transactions = []
        ip_address = request.META.get("REMOTE_ADDR")
        for vid in ids:
            v = existing_map.get(vid)
            if v is None:
                skipped += 1
                continue
            if not can_president_act(v.verification_status):
                skipped += 1
                continue

            if decision == Status.APPROVED:
                v.verification_status = Status.APPROVED
                v.approved_at = timezone.now()
                action_str = "APPROVED"
            else:
                v.verification_status = "Rejected"
                action_str = "REJECTED"

            v.president_id_FK = officer
            v.save()

            if decision == "Approved":
                archive = archive_transaction(v.table_name, v.record_id, officer)
                if archive and v.table_name in ("membership_fee", "monthly_dues"):
                    fund_transactions.append(
                        FundTransaction(
                            direction="inflow",
                            amount=archive.amount,
                            source_type=v.table_name,
                            source_id=v.record_id,
                            description=f"{archive.member_name} ({dict(FundTransaction.SOURCE_TYPES).get(v.table_name, v.table_name)})",
                            recorded_by_user_id_FK=officer,
                        )
                    )

            audit_entries.append({
                "table": v.table_name,
                "record_id": v.record_id,
                "action": action_str,
                "ip": ip_address,
                "notes": remarks.strip() if remarks else None,
            })
            processed += 1

        if audit_entries:
            _record_bulk_audit_trail(audit_entries, actor=officer)

        if fund_transactions:
            FundTransaction.objects.bulk_create(fund_transactions)

        _broadcast_pending_counts()
        return JsonResponse({
            "success": True,
            "processed": processed,
            "skipped": skipped,
            "message": f"Processed {processed} entr{processed == 1 and 'y' or 'ies'} ({skipped} skipped).",
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_POST
@transaction.atomic
def submit_presidential_aid_decision_batch(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard
    try:
        body = json.loads(request.body)
        ids = body.get("ids", [])
        decision = (body.get("decision") or "").strip()
        remarks = (body.get("remarks") or "").strip()

        if not ids or not isinstance(ids, list):
            return JsonResponse({"success": False, "message": "ids must be a non-empty array."}, status=400)
        if decision not in {"Approved", "Rejected"}:
            return JsonResponse({"success": False, "message": "Invalid decision. Use Approved or Rejected."}, status=400)
        if decision == "Rejected" and not remarks:
            return JsonResponse({"success": False, "message": "Remarks are mandatory for rejections."}, status=400)

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({"success": False, "message": "Officer session missing."}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))

        table_record_pairs = []
        for raw_id in ids:
            if not isinstance(raw_id, str):
                return JsonResponse({"success": False, "message": "Invalid id format."}, status=400)
            if raw_id.startswith("medical-"):
                table_name = "medical_aid"
                record_id = raw_id.replace("medical-", "")
            elif raw_id.startswith("death-"):
                table_name = "death_aid"
                record_id = raw_id.replace("death-", "")
            else:
                return JsonResponse({"success": False, "message": f"Invalid id format: {raw_id}"}, status=400)
            try:
                table_record_pairs.append((table_name, int(record_id)))
            except ValueError:
                return JsonResponse({"success": False, "message": f"Invalid record id in: {raw_id}"}, status=400)

        from collections import defaultdict
        from itertools import chain
        table_ids = defaultdict(list)
        for tn, rid in table_record_pairs:
            table_ids[tn].append(rid)

        verifications = TransactionVerification.objects.select_for_update().filter(
            table_name__in=list(table_ids.keys()),
            record_id__in=set(chain.from_iterable(table_ids.values())),
        )
        existing_map = {}
        for tv in verifications:
            key = (tv.table_name, tv.record_id)
            existing_map[key] = tv

        active_members = Member.objects.exclude(
            membership_status__iexact="Retired",
        )
        active_members_count = active_members.count()

        processed = 0
        skipped = 0
        audit_entries = []
        ip_address = request.META.get("REMOTE_ADDR")
        for tn, rid in table_record_pairs:
            v = existing_map.get((tn, rid))
            if v is None:
                skipped += 1
                continue
            if not can_president_act(v.verification_status):
                skipped += 1
                continue

            canonical_decision = Status.APPROVED if is_approved(decision) else Status.REJECTED

            record = None
            if v.table_name == "medical_aid":
                record = MedicalAid.objects.filter(medical_aid_id_PK=v.record_id).first()
            elif v.table_name == "death_aid":
                record = DeathAid.objects.filter(death_aid_id_PK=v.record_id).first()

            if record is not None:
                record.president_decided_by_user_id_FK = officer
                record.president_decision = decision
                record.status = canonical_decision
                record.save(update_fields=[
                    "president_decided_by_user_id_FK",
                    "president_decision",
                    "status",
                ])

            v.verification_status = canonical_decision
            if is_approved(decision):
                v.approved_at = timezone.now()

            v.president_id_FK = officer
            v.save()

            if is_approved(decision):
                archive = archive_transaction(v.table_name, v.record_id, officer)

                if archive is not None:
                    relationship = ""
                    if v.table_name == "death_aid" and record is not None:
                        relationship = getattr(record, "relationship_to_member", "")

                    per_member_amount = get_contribution_amount_for_aid(v.table_name, relationship)
                    total_expected = active_members_count * per_member_amount

                    if AidTrackingPost.objects.filter(
                        source_type=v.table_name,
                        source_id=v.record_id,
                    ).exists():
                        skipped += 1
                        continue

                    post = AidTrackingPost.objects.create(
                        archive_id_FK=archive,
                        aid_type=v.table_name,
                        target_month=timezone.now().strftime("%Y-%m"),
                        total_expected=total_expected,
                        total_collected=0,
                        source_type=v.table_name,
                        source_id=v.record_id,
                        created_by_user_id_FK=officer,
                    )

                    Contribution.objects.bulk_create([
                        Contribution(
                            aid_tracking_post_id_FK=post,
                            member_id_FK=member,
                            expected_amount=per_member_amount,
                            paid_amount=0,
                            status="NOT_PAID",
                        )
                        for member in active_members
                    ])

                    transaction.on_commit(
                        lambda r=record, tn=v.table_name, pm=per_member_amount: queue_aid_emails(r, tn, pm)
                    )

                    member_name = record.member_id_FK.full_name if record is not None and hasattr(record, "member_id_FK") and record.member_id_FK else ""
                    payload = {
                        "type": "aid_post_created",
                        "post_id": post.post_id_PK,
                        "member_name": member_name,
                        "aid_type": v.table_name,
                        "total_expected": float(total_expected),
                        "target_month": post.target_month,
                    }
                    _broadcast_to_group("auditor_dashboard", payload)
                    _broadcast_to_group("treasurer_dashboard", payload)

            audit_entries.append({
                "table": v.table_name,
                "record_id": v.record_id,
                "action": "APPROVED" if decision == "Approved" else "REJECTED",
                "ip": ip_address,
                "notes": remarks.strip() if remarks else None,
            })
            processed += 1

        if audit_entries:
            _record_bulk_audit_trail(audit_entries, actor=officer)

        _broadcast_pending_counts()
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})
        transaction.on_commit(
            lambda: threading.Thread(target=process_email_queue, kwargs={"batch_size": 5}).start()
        )
        return JsonResponse({
            "success": True,
            "processed": processed,
            "skipped": skipped,
            "message": f"Processed {processed} entr{processed == 1 and 'y' or 'ies'} ({skipped} skipped).",
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_GET
def president_kpi_counts(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    verified_dues_count = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).count()

    medical_pending = MedicalAid.objects.filter(
        status="Auditor Verified",
        president_decided_by_user_id_FK__isnull=True,
    ).count()
    death_pending = DeathAid.objects.filter(
        status="Auditor Verified",
        president_decided_by_user_id_FK__isnull=True,
    ).count()
    verified_claims_count = medical_pending + death_pending

    verified_contributions_count = TransactionVerification.objects.filter(
        table_name="contribution",
        target_category="aid_contribution",
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).count()

    payment_decisions = TransactionVerification.objects.filter(
        president_id_FK__isnull=False,
    ).count()
    aid_decisions = MedicalAid.objects.filter(
        president_decided_by_user_id_FK__isnull=False,
    ).count() + DeathAid.objects.filter(
        president_decided_by_user_id_FK__isnull=False,
    ).count()
    contribution_decisions = TransactionVerification.objects.filter(
        table_name="contribution",
        president_id_FK__isnull=False,
    ).count()
    total_approvals_count = payment_decisions + aid_decisions + contribution_decisions

    today = timezone.localdate()
    dept_summary = dues_compliance_summary(today.year, today.month)
    total_active = sum(d["total_members"] for d in dept_summary)
    total_paid = sum(d["paid_count"] for d in dept_summary)
    total_unpaid = sum(d["unpaid_count"] for d in dept_summary)
    overall_pct = round(total_paid / total_active * 100, 1) if total_active else 0.0
    low_depts = [
        {"id": d["department_id"], "name": d["department_name"], "pct": d["percentage"]}
        for d in dept_summary if d["percentage"] < 70
    ]
    sorted_depts = sorted(dept_summary, key=lambda d: d["percentage"], reverse=True)
    top_depts = [{"name": d["department_name"], "pct": d["percentage"]} for d in sorted_depts[:3]]
    bottom_depts = [{"name": d["department_name"], "pct": d["percentage"]} for d in sorted_depts[-3:]] if len(sorted_depts) >= 3 else []

    return JsonResponse({
        "ok": True,
        "verified_dues_count": verified_dues_count,
        "verified_claims_count": verified_claims_count,
        "verified_contributions_count": verified_contributions_count,
        "total_approvals_count": total_approvals_count,
        "total_active_members": total_active,
        "overall_compliance_percentage": overall_pct,
        "total_paid": total_paid,
        "total_unpaid": total_unpaid,
        "departments_below_threshold": low_depts,
        "top_performing_departments": top_depts,
        "bottom_performing_departments": bottom_depts,
    })


# ============================================================================
# PRESIDENT: AID TRACKING POST FINISH APPROVAL
# ============================================================================


@require_GET
def president_pending_finish_requests(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(
        finish_status__in=["pending_approval", "pending_president"], is_active=True
    ).select_related(
        "archive_id_FK",
        "archive_id_FK__member_id_FK",
        "created_by_user_id_FK",
    ).all()

    items = []
    for post in posts:
        archive = post.archive_id_FK
        member = archive.member_id_FK if archive else None
        aid_label = "Medical Aid" if post.aid_type == "medical_aid" else "Death Aid"
        collection_rate = 0
        if post.total_expected > 0:
            collection_rate = round(float(post.total_collected) / float(post.total_expected) * 100, 1)

        items.append({
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "aid_label": aid_label,
            "member_name": archive.member_name if archive else "",
            "member_id": member.member_id_PK if member else None,
            "target_month": post.target_month,
            "total_expected": str(post.total_expected),
            "total_collected": str(post.total_collected),
            "collection_rate": collection_rate,
            "skip_remaining": post.finish_skip_remaining,
            "status": archive.status if archive else "",
            "amount": str(archive.amount) if archive else "0",
            "created_by": post.created_by_user_id_FK.full_name if post.created_by_user_id_FK else "",
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "verified_by_auditor": post.finish_status == "pending_president",
        })

    return JsonResponse({"ok": True, "posts": items})


@require_GET
def president_finish_request_details(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    post_id = request.GET.get("post_id", "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "post_id required."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id))
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Post not found."}, status=404)

    contributions = Contribution.objects.filter(
        aid_tracking_post_id_FK=post
    ).select_related("member_id_FK").order_by("member_id_FK__full_name")

    details = []
    total_paid = 0
    paid_count = 0
    for c in contributions:
        member_name = c.member_id_FK.full_name if c.member_id_FK else "Unknown"
        paid = float(c.paid_amount) if c.paid_amount else 0
        expected = float(c.expected_amount) if c.expected_amount else 0
        if c.status == "PAID":
            total_paid += paid
            paid_count += 1
        details.append({
            "member_name": member_name,
            "expected_amount": expected,
            "paid_amount": paid,
            "status": c.status,
            "payment_date": c.payment_date.isoformat() if c.payment_date else None,
        })

    return JsonResponse({
        "ok": True,
        "post_id": post.post_id_PK,
        "aid_type": post.aid_type,
        "target_month": post.target_month,
        "total_expected": float(post.total_expected),
        "total_paid": round(total_paid, 2),
        "paid_count": paid_count,
        "total_count": contributions.count(),
        "details": details,
    })


@require_POST
@transaction.atomic
def president_approve_aid_post_finish(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    president_id = request.session.get("officer_id")
    if president_id is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)
    try:
        president = OfficerUser.objects.get(user_id_PK=int(president_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    post_id = (request.POST.get("post_id") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(
            post_id_PK=int(post_id), is_active=True,
            finish_status__in=["pending_approval", "pending_president"],
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Pending finish request not found."}, status=404)

    if post.finish_skip_remaining and not post.finish_paid_with_funds:
        Contribution.objects.filter(
            aid_tracking_post_id_FK=post,
            status="NOT_PAID",
        ).update(
            status="SKIPPED",
            is_manually_overridden=True,
            paid_amount=0,
        )
        totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
            total_collected=Sum("paid_amount"),
        )
        post.total_collected = totals["total_collected"] or 0

    was_auditor_verified = post.finish_status == "pending_president"

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""

    if was_auditor_verified:
        pending_ids = list(
            Contribution.objects.filter(
                aid_tracking_post_id_FK=post,
                status="PENDING_VERIFICATION",
            ).values_list("contribution_id_PK", flat=True)
        )
        if pending_ids:
            Contribution.objects.filter(contribution_id_PK__in=pending_ids).update(status="PAID")
            totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
                total_collected=Sum("paid_amount"),
            )
            post.total_collected = totals["total_collected"] or 0

        post.finish_status = "pending_release"
        post.save(update_fields=["finish_status", "total_collected"])

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_APPROVED",
            actor=president,
            new={"finish_status": "pending_release"},
            ip=request.META.get("REMOTE_ADDR"),
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
            "type": "aid_post_release_pending",
            "post_id": post.post_id_PK,
            "member_name": member_name,
        })
        async_to_sync(channel_layer.group_send)("auditor_dashboard", {
            "type": "data_changed", "section": "aids",
        })
        async_to_sync(channel_layer.group_send)("president_dashboard", {
            "type": "data_changed", "section": "aids",
        })

        return JsonResponse({"ok": True, "message": "Finish approved. The Treasurer must now release the funds to close this post."})
    else:
        post.finish_status = "approved"
        post.is_active = False
        post.save(update_fields=["finish_status", "is_active", "total_collected"])

        if archive is not None:
            if archive.transaction_type == "death_aid":
                DeathAid.objects.filter(death_aid_id_PK=archive.record_id).update(status="Released")
            elif archive.transaction_type == "medical_aid":
                MedicalAid.objects.filter(medical_aid_id_PK=archive.record_id).update(status="Released")

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_APPROVED",
            actor=president,
            new={"finish_status": "approved", "is_active": False},
            ip=request.META.get("REMOTE_ADDR"),
        )

        channel_layer = get_channel_layer()
        payload = {
            "type": "aid_post_finished",
            "post_id": post.post_id_PK,
            "member_name": member_name,
        }
        async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
        async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
        async_to_sync(channel_layer.group_send)("president_dashboard", payload)

        return JsonResponse({"ok": True, "message": "Finish request approved. Post moved to history."})


@require_POST
@transaction.atomic
def president_reject_aid_post_finish(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    president_id = request.session.get("officer_id")
    if president_id is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)
    try:
        president = OfficerUser.objects.get(user_id_PK=int(president_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    post_id = (request.POST.get("post_id") or "").strip()
    remarks = (request.POST.get("remarks") or "").strip()

    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(
            post_id_PK=int(post_id), is_active=True,
            finish_status__in=["pending_approval", "pending_president"],
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Pending finish request not found."}, status=404)

    post.finish_status = "rejected"
    post.save(update_fields=["finish_status"])

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="FINISH_REJECTED",
        actor=president,
        new={"finish_status": "rejected"},
        notes=remarks,
        ip=request.META.get("REMOTE_ADDR"),
    )

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""
    channel_layer = get_channel_layer()
    payload = {
        "type": "aid_post_finish_rejected",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "remarks": remarks,
    }
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("president_dashboard", payload)

    return JsonResponse({"ok": True, "message": "Finish request rejected. Post returned to active state."})


# ==========================================================================
# PAYROLL BATCH APPROVAL (PRESIDENT)
# ==========================================================================


@require_GET
def president_pending_payroll_batches(request: HttpRequest):
    """List auditor-verified PayrollBatches pending presidential approval."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    batches = PayrollBatch.objects.filter(
        status="Auditor Verified",
    ).select_related(
        "recorded_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
    ).order_by("-created_at")

    fund_balance = float(FundTransaction.get_balance())
    safety_threshold = float(SystemSetting.objects.get_or_create(
        setting_key="safety_threshold", defaults={"setting_value": "20000"}
    )[0].setting_value)

    items = []
    for b in batches:
        fund_impact = PayrollDeduction.objects.filter(
            batch_id_FK=b, fund_impact="inflow"
        ).aggregate(total=Sum("amount"))["total"] or 0
        projected = fund_balance + float(fund_impact)

        items.append({
            "batch_id": b.batch_id_PK,
            "payroll_period": b.payroll_period,
            "total_amount": float(b.total_amount),
            "member_count": b.member_count,
            "fund_impact": float(fund_impact),
            "projected_balance": projected,
            "notes": b.notes or "",
            "recorded_by": b.recorded_by_user_id_FK.full_name if b.recorded_by_user_id_FK else "",
            "verified_by": b.auditor_verified_by_user_id_FK.full_name if b.auditor_verified_by_user_id_FK else "",
            "created_at": b.created_at.isoformat() if b.created_at else "",
        })

    return JsonResponse({
        "ok": True,
        "batches": items,
        "fund_balance": fund_balance,
        "safety_threshold": safety_threshold,
    })


@require_GET
def president_payroll_batch_detail(request: HttpRequest, batch_id: int):
    """View a PayrollBatch with fund balance context."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id)
    deductions = PayrollDeduction.objects.filter(batch_id_FK=batch).select_related("member_id_FK")

    fund_balance = float(FundTransaction.get_balance())
    fund_impact = deductions.filter(fund_impact="inflow").aggregate(
        total=Sum("amount")
    )["total"] or 0
    projected = fund_balance + float(fund_impact)
    safety_threshold = float(SystemSetting.objects.get_or_create(
        setting_key="safety_threshold", defaults={"setting_value": "20000"}
    )[0].setting_value)

    ded_list = []
    for d in deductions:
        ded_list.append({
            "deduction_id": d.deduction_id_PK,
            "member_id": d.member_id_FK.member_id_PK,
            "member_name": d.member_id_FK.full_name,
            "amount": float(d.amount),
            "category": d.category,
            "fund_impact": d.fund_impact,
            "month_covered": d.month_covered or "",
        })

    return JsonResponse({
        "ok": True,
        "batch": {
            "batch_id": batch.batch_id_PK,
            "payroll_period": batch.payroll_period,
            "total_amount": float(batch.total_amount),
            "member_count": batch.member_count,
            "hardcopy_reference": batch.hardcopy_reference or "",
            "notes": batch.notes or "",
            "status": batch.status,
            "recorded_by": batch.recorded_by_user_id_FK.full_name if batch.recorded_by_user_id_FK else "",
            "verified_by": batch.auditor_verified_by_user_id_FK.full_name if batch.auditor_verified_by_user_id_FK else "",
            "auditor_remarks": batch.auditor_remarks or "",
            "created_at": batch.created_at.isoformat() if batch.created_at else "",
        },
        "deductions": ded_list,
        "fund_balance": fund_balance,
        "fund_impact": float(fund_impact),
        "projected_balance": projected,
        "safety_threshold": safety_threshold,
        "is_safe": projected >= safety_threshold,
    })


@require_POST
@transaction.atomic
def president_approve_payroll_batch(request: HttpRequest, batch_id: int):
    """Approve a PayrollBatch — creates FundTransaction entries and archives."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id, status="Auditor Verified")

    stored_officer_id = request.session.get("officer_id")
    try:
        president = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (ValueError, OfficerUser.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    remarks = data.get("remarks", "")

    # Approve the batch
    batch.status = "Approved"
    batch.president_approved_by_user_id_FK = president
    batch.president_approved_at = timezone.now()
    batch.president_remarks = remarks
    batch.save(update_fields=[
        "status", "president_approved_by_user_id_FK",
        "president_approved_at", "president_remarks",
    ])

    # Create FundTransaction for each deduction with fund_impact="inflow"
    inflow_deductions = PayrollDeduction.objects.filter(
        batch_id_FK=batch, fund_impact="inflow"
    ).select_related("member_id_FK")

    ft_count = 0
    for d in inflow_deductions:
        description = _build_payroll_deduction_description(d)
        FundTransaction.objects.create(
            direction="inflow",
            amount=d.amount,
            source_type="payroll_batch",
            source_id=batch.pk,
            description=description,
            reference_number=batch.hardcopy_reference or "",
            recorded_by_user_id_FK=president,
        )
        ft_count += 1

        # If aid contribution, update the Contribution record for tracking
        if d.category == "aid_contribution" and d.aid_tracking_post_id_FK:
            Contribution.objects.update_or_create(
                aid_tracking_post_id_FK=d.aid_tracking_post_id_FK,
                member_id_FK=d.member_id_FK,
                defaults={
                    "paid_amount": d.amount,
                    "payment_date": timezone.now().date(),
                    "status": "PAID",
                    "updated_by_user_id_FK": president,
                },
            )

    # Archive the batch
    archive_transaction(table_name="payroll_batch", pk=batch.pk, officer=president)

    fund_balance = float(FundTransaction.get_balance())

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="APPROVED",
        actor=president,
        new={
            "status": "Approved",
            "total_amount": float(batch.total_amount),
            "fund_impact_count": ft_count,
            "remarks": remarks,
        },
        ip=request.META.get("REMOTE_ADDR"),
    )

    _broadcast_pending_counts()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
        "type": "dashboard_refresh", "section": "payroll_batches",
    })
    async_to_sync(channel_layer.group_send)("president_dashboard", {
        "type": "dashboard_refresh", "section": "all",
    })

    return JsonResponse({
        "ok": True,
        "message": "Payroll batch approved.",
        "fund_balance": fund_balance,
        "fund_transactions_created": ft_count,
    })


@require_POST
@transaction.atomic
def president_reject_payroll_batch(request: HttpRequest, batch_id: int):
    """Reject a PayrollBatch."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id, status="Auditor Verified")

    stored_officer_id = request.session.get("officer_id")
    try:
        president = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (ValueError, OfficerUser.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    reason = data.get("reason", "")
    batch.status = "Rejected"
    batch.president_approved_by_user_id_FK = president
    batch.president_remarks = reason
    batch.save(update_fields=["status", "president_approved_by_user_id_FK", "president_remarks"])

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="REJECTED",
        actor=president,
        new={"status": "Rejected", "reason": reason},
        ip=request.META.get("REMOTE_ADDR"),
    )

    _broadcast_pending_counts()

    return JsonResponse({"ok": True, "message": "Payroll batch rejected."})


def _build_payroll_deduction_description(deduction: PayrollDeduction) -> str:
    """Build a human-readable description for a PayrollDeduction FundTransaction."""
    member = deduction.member_id_FK
    member_name = member.full_name if member else "Unknown"
    if deduction.category == "monthly_dues":
        period = deduction.month_covered or ""
        return f"Monthly dues {period} — {member_name}"
    elif deduction.category == "membership_fee":
        return f"Membership fee — {member_name}"
    elif deduction.category == "aid_contribution":
        post_ref = ""
        if deduction.aid_tracking_post_id_FK:
            post = deduction.aid_tracking_post_id_FK
            post_ref = f" ({post.aid_type}#{post.source_id})"
        return f"Aid contribution{post_ref} — {member_name}"
    return f"Deduction — {member_name}"


# ==========================================================================
# BYLAWS CONSTANTS MANAGEMENT
# ==========================================================================


def _resolve_president(request: HttpRequest):
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return None
    try:
        return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except Exception:
        return None


def _parse_iso_date(value: Any):
    raw_value = (value or "").strip() if isinstance(value, str) else value
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value)).date()
    except (TypeError, ValueError):
        return None


def _officer_to_json(officer: OfficerUser) -> Dict[str, Any]:
    department = getattr(officer, "department_id_FK", None)
    return {
        "id": officer.user_id_PK,
        "full_name": officer.full_name,
        "username": officer.username,
        "role": officer.role,
        "account_status": officer.account_status,
        "term_start": officer.term_start.isoformat() if officer.term_start else "",
        "term_end": officer.term_end.isoformat() if officer.term_end else "",
        "department_id": department.department_id_PK if department else None,
        "department_name": department.name if department else "",
        "department_code": department.code if department else "",
        "mfa_enabled": bool(officer.mfa_enabled),
        "created_at": officer.created_at.isoformat() if officer.created_at else "",
        "updated_at": officer.updated_at.isoformat() if officer.updated_at else "",
    }


def _extract_request_data(request: HttpRequest) -> Dict[str, Any]:
    if request.content_type and "json" in request.content_type.lower():
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    if request.body:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return request.POST.dict()


@require_GET
def president_officers_list(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officers = OfficerUser.objects.select_related("department_id_FK").order_by("-created_at", "full_name")
    return JsonResponse({"ok": True, "officers": [_officer_to_json(officer) for officer in officers]})


@require_POST
@transaction.atomic
def president_officers_create(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    payload = _extract_request_data(request)
    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "Officer").strip()
    account_status = (payload.get("account_status") or "Active").strip() or "Active"
    term_start = _parse_iso_date(payload.get("term_start"))
    term_end = _parse_iso_date(payload.get("term_end"))
    department_id = payload.get("department_id") or payload.get("department") or None

    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)
    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not password:
        return JsonResponse({"ok": False, "error": "Password is required."}, status=400)

    if OfficerUser.objects.filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)

    department = None
    if department_id not in (None, "", 0, "0"):
        department = Department.objects.filter(department_id_PK=int(department_id)).first()
        if department is None:
            return JsonResponse({"ok": False, "error": "Selected department was not found."}, status=400)

    officer = OfficerUser.objects.create(
        full_name=full_name,
        username=username,
        password_hash=sha256_hex(password),
        role=role,
        department_id_FK=department,
        account_status=account_status,
        term_start=term_start,
        term_end=term_end,
    )

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="CREATED",
        actor=president,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Created officer account for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officers_update(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = get_object_or_404(OfficerUser.objects.select_related("department_id_FK"), pk=officer_id)
    payload = _extract_request_data(request)

    username = (payload.get("username") or officer.username).strip()
    full_name = (payload.get("full_name") or officer.full_name).strip()
    role = (payload.get("role") or officer.role).strip()
    account_status = (payload.get("account_status") or officer.account_status).strip()
    term_start = _parse_iso_date(payload.get("term_start")) if payload.get("term_start") not in (None, "") else officer.term_start
    term_end = _parse_iso_date(payload.get("term_end")) if payload.get("term_end") not in (None, "") else officer.term_end
    password = (payload.get("password") or "").strip()
    department_id = payload.get("department_id") or payload.get("department")

    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)

    if OfficerUser.objects.exclude(pk=officer.pk).filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)

    department = officer.department_id_FK
    if department_id not in (None, "", 0, "0"):
        department = Department.objects.filter(department_id_PK=int(department_id)).first()
        if department is None:
            return JsonResponse({"ok": False, "error": "Selected department was not found."}, status=400)
    elif department_id in ("", None):
        department = None if payload.get("clear_department") else department

    officer.full_name = full_name
    officer.username = username
    officer.role = role
    officer.account_status = account_status
    officer.term_start = term_start
    officer.term_end = term_end
    officer.department_id_FK = department
    if password:
        officer.password_hash = sha256_hex(password)

    update_fields = [
        "full_name",
        "username",
        "role",
        "account_status",
        "term_start",
        "term_end",
        "department_id_FK",
        "updated_at",
    ]
    if password:
        update_fields.append("password_hash")
    officer.save(update_fields=update_fields)

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="UPDATED",
        actor=president,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Updated officer account for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officers_reset_password(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = get_object_or_404(OfficerUser, pk=officer_id)
    temp_password = secrets.token_urlsafe(10)
    officer.password_hash = sha256_hex(temp_password)
    officer.save(update_fields=["password_hash", "updated_at"])

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="PASSWORD_RESET",
        actor=president,
        new={"username": officer.username, "temp_password_generated": True},
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Reset password for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "temp_password": temp_password, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officers_deactivate(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = get_object_or_404(OfficerUser, pk=officer_id)
    officer.account_status = "Inactive"
    officer.save(update_fields=["account_status", "updated_at"])

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="DEACTIVATED",
        actor=president,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Deactivated officer account for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_GET
def president_profile(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_profile_update(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    payload = _extract_request_data(request)
    full_name = (payload.get("full_name") or officer.full_name).strip()
    username = (payload.get("username") or officer.username).strip()
    password = (payload.get("password") or "").strip()

    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)
    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)

    if OfficerUser.objects.exclude(pk=officer.pk).filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)

    officer.full_name = full_name
    officer.username = username
    if password:
        officer.password_hash = sha256_hex(password)

    update_fields = ["full_name", "username", "updated_at"]
    if password:
        update_fields.append("password_hash")
    officer.save(update_fields=update_fields)

    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="PROFILE_UPDATED",
        actor=officer,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes="Updated own officer profile",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officer_self_enroll(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = resolve_officer_from_session(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    payload = _extract_request_data(request)
    employee_id = (payload.get("employee_id") or payload.get("prof_id") or "").strip()
    department_id = payload.get("department_id") or payload.get("prof_dept") or None
    department_name = (payload.get("department_name") or payload.get("department") or "").strip()
    position = (payload.get("position") or payload.get("prof_pos") or president.role or "Officer").strip()
    contact_number = (payload.get("contact_number") or payload.get("prof_contact") or "").strip() or None
    email = (payload.get("email") or payload.get("prof_email") or "").strip() or None

    if not employee_id:
        return JsonResponse({"ok": False, "error": "Employee ID is required."}, status=400)

    if Member.objects.filter(employee_id=employee_id).exists():
        return JsonResponse({"ok": False, "error": "Employee ID is already registered."}, status=409)
    if Member.objects.filter(officer_user_id_FK=president).exists():
        return JsonResponse({"ok": False, "error": "This officer is already linked to a member profile."}, status=409)

    department = president.department_id_FK
    if department_id not in (None, "", 0, "0"):
        department = Department.objects.filter(department_id_PK=int(department_id)).first() or department
    elif department_name:
        department = Department.objects.filter(name__iexact=department_name).first() or department

    member = Member.objects.create(
        full_name=president.full_name,
        employee_id=employee_id,
        officer_user_id_FK=president,
        department=department.name if department else department_name or None,
        department_id_FK=department,
        position=position,
        contact_number=contact_number,
        email=email,
        employment_status="Active",
        membership_status="Pending",
        member_type="Officer-Member",
        date_joined=timezone.now().date(),
    )

    fee = MembershipFee.objects.create(
        member_id_FK=member,
        amount=str(get_membership_fee_amount()),
        payment_method="Pending",
        payment_status="Pending",
        payment_date=timezone.now().date(),
        receipt_number=f"OFFICER-SELF-{int(timezone.now().timestamp())}",
        recorded_by_user_id_FK=president,
    )
    TransactionVerification.objects.create(
        table_name="membership_fee",
        record_id=fee.fee_id_PK,
        verification_status="Pending",
    )

    _record_audit_trail(
        table="member",
        record_id=member.member_id_PK,
        action="CREATED",
        actor=president,
        new={
            "member_id": member.member_id_PK,
            "full_name": member.full_name,
            "employee_id": member.employee_id,
            "department": member.department or "",
            "position": member.position or "",
            "member_type": member.member_type,
            "officer_user_id": president.user_id_PK,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes="Officer self-enrolled as member",
    )

    _record_audit_trail(
        table="membership_fee",
        record_id=fee.fee_id_PK,
        action="CREATED",
        actor=president,
        new={
            "member_id": member.member_id_PK,
            "amount": str(fee.amount),
            "payment_status": fee.payment_status,
            "receipt_number": fee.receipt_number,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes="Auto-generated membership fee for officer self-enrollment",
    )

    _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "members"})

    return JsonResponse({"ok": True, "member": {"member_id": member.member_id_PK, "employee_id": member.employee_id, "full_name": member.full_name}})


@require_GET
def get_policy_constants(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)

    defaults = {
        "membership_fee": float(POLICY.membership_fee),
        "monthly_dues": float(POLICY.monthly_dues),
        "accidental_sickness_aid_threshold": float(POLICY.accidental_sickness_aid_threshold),
        "accidental_sickness_aid_benefit": float(POLICY.accidental_sickness_aid_benefit),
        "death_aid_member": float(POLICY.death_aid_member),
        "death_aid_spouse": float(POLICY.death_aid_spouse),
        "death_aid_parent_child": float(POLICY.death_aid_parent_child),
        "death_aid_full_blood_sibling": float(POLICY.death_aid_full_blood_sibling),
    }

    overrides = {}
    for key in defaults:
        raw = _get_setting_override(key)
        if raw is not None:
            try:
                overrides[key] = float(raw)
            except (TypeError, ValueError):
                overrides[key] = defaults[key]
        else:
            overrides[key] = defaults[key]

    _record_audit_trail(
        table="policy_constants",
        record_id=0,
        action="READ",
        actor=president,
        ip=request.META.get("REMOTE_ADDR"),
        notes="Retrieved policy constants snapshot",
    )

    return JsonResponse({
        "ok": True,
        "constants": overrides,
        "defaults": defaults,
    })


@require_POST
@transaction.atomic
def update_policy_constant(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)

    key = (data.get("key") or "").strip()
    value_raw = data.get("value")

    allowed_keys = {k for k, _, _ in _POLICY_CONSTANT_KEYS}
    if key not in allowed_keys:
        return JsonResponse({"ok": False, "error": f"Unknown constant key: {key}"}, status=400)

    try:
        new_value = float(value_raw)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Value must be a number."}, status=400)

    if new_value < 0:
        return JsonResponse({"ok": False, "error": "Value cannot be negative."}, status=400)

    old_value = None
    setting_key = f"{_POLICY_OVERRIDE_PREFIX}{key}"
    row, _ = SystemSetting.objects.get_or_create(
        setting_key=setting_key,
        defaults={"setting_value": str(new_value)},
    )
    old_value = row.setting_value
    row.setting_value = str(new_value)
    row.save(update_fields=["setting_value", "updated_at"])

    _record_audit_trail(
        table="policy_constants",
        record_id=0,
        action="UPDATED",
        actor=president,
        old={"key": key, "value": old_value},
        new={"key": key, "value": str(new_value)},
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Updated policy constant {key}",
    )

    return JsonResponse({
        "ok": True,
        "message": f"Constant {key} updated to ₱{new_value:,.2f}",
        "key": key,
        "value": new_value,
    })


@require_GET
def bylaws_files_api(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    files = BylawsFile.objects.all().order_by("-uploaded_at")

    data = []
    for f in files:
        data.append({
            "document_id": f.bylaws_file_id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "uploaded_at": f.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if f.uploaded_at else None,
            "uploaded_by": f.uploaded_by_user_id_FK.full_name if f.uploaded_by_user_id_FK else "System",
            "verification_status": f.verification_status,
        })

    _record_audit_trail(
        table="bylaws_documents",
        record_id=0,
        action="READ",
        actor=president,
        ip=request.META.get("REMOTE_ADDR"),
        notes="Listed bylaws document archive",
    )

    return JsonResponse({"ok": True, "files": data})


@require_POST
@transaction.atomic
def upload_bylaws_file(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    uploaded_file = request.FILES.get("bylaws_file")
    if not uploaded_file:
        return JsonResponse({"ok": False, "error": "No file uploaded."}, status=400)

    allowed_types = {"application/pdf", "text/plain", "application/msword",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if uploaded_file.content_type not in allowed_types:
        return JsonResponse({"ok": False, "error": f"Unsupported file type: {uploaded_file.content_type}"}, status=400)

    max_size = 10 * 1024 * 1024
    if uploaded_file.size > max_size:
        return JsonResponse({"ok": False, "error": "File size exceeds 10MB limit."}, status=400)

    file_bytes = uploaded_file.read()
    file_hash = ""
    try:
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        file_hash = hasher.hexdigest()
    except Exception:
        file_hash = ""

    doc = BylawsFile.objects.create(
        file_name=uploaded_file.name,
        file_type=uploaded_file.content_type or "",
        file_data=file_bytes,
        file_size=uploaded_file.size or 0,
        file_hash=file_hash or "",
        verification_status="Active",
        uploaded_by_user_id_FK=president,
    )

    _record_audit_trail(
        table="bylaws_documents",
        record_id=doc.bylaws_file_id,
        action="UPLOADED",
        actor=president,
        new={
            "file_name": uploaded_file.name,
            "file_type": uploaded_file.content_type,
            "file_size": uploaded_file.size,
            "file_hash": file_hash,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Uploaded bylaws file: {uploaded_file.name}",
    )

    return JsonResponse({
        "ok": True,
        "message": f"Bylaws file '{uploaded_file.name}' uploaded successfully.",
        "document_id": doc.bylaws_file_id,
        "file_name": uploaded_file.name,
    })


@require_POST
@transaction.atomic
def delete_bylaws_file(request: HttpRequest, document_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    doc = get_object_or_404(BylawsFile, pk=document_id)
    old_values = {
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "verification_status": doc.verification_status,
    }

    doc.delete()

    _record_audit_trail(
        table="bylaws_documents",
        record_id=document_id,
        action="DELETED",
        actor=president,
        old=old_values,
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Deleted bylaws file: {old_values.get('file_name')}",
    )

    return JsonResponse({"ok": True, "message": "Bylaws file deleted successfully."})

