import json
from typing import Any, Dict, List

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core_system.guards import require_role
from core_system.models import (
    Member,
    MembershipFee,
    MonthlyDues,
    MedicalAid,
    DeathAid,
    OfficerUser,
    TransactionVerification,
    FinancialDocumentArchive,
    GlobalAuditTrail,
    TransactionArchive,
    AidTrackingPost,
    Contribution,
)
from core_system.constants.status_constants import Status, can_president_act, is_approved, is_rejected
from core_system.constants.policy_constants import (
    get_death_aid_amount,
    get_membership_fee_amount,
    get_monthly_dues_amount,
    get_contribution_amount_for_aid,
    is_exempt_from_dues_and_aid,
)
from core_system.shared_view_utils import (
    MODEL_MAP,
    _audit_evidence_filename,
    _get_auditor_verification,
    _record_audit_trail,
    _log_sensitive_read,
    _payment_item_to_json,
    archive_transaction,
    _broadcast_pending_counts,
    _broadcast_to_group,
)


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
        "covered_period": payment_record.month_covered or "Initial Setup",
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
        "membership_month": payment_record.month_covered or "",
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
            archive_transaction(
                verification.table_name,
                verification.record_id,
                officer,
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
def submit_presidential_aid_decision(request):
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

        record.president_decided_by_user_id_FK = officer
        record.president_decision = decision
        record.status = decision
        extra_fields = ["president_decided_by_user_id_FK", "president_decision", "status"]
        if table_name == "medical_aid" and decision == "Approved" and approved_amount:
            record.validated_aid_amount = approved_amount
            extra_fields.append("validated_aid_amount")
        record.save(update_fields=extra_fields)
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})

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
            active_count = active_members.count()
            total_expected = active_count * per_member_amount

            post = AidTrackingPost.objects.create(
                archive_id_FK=archive,
                aid_type=table_name,
                target_month=timezone.now().strftime("%Y-%m"),
                total_expected=total_expected,
                total_collected=0,
                created_by_user_id_FK=officer,
            )

            contribution_records = []
            for member in active_members:
                contribution_records.append(
                    Contribution(
                        aid_tracking_post_id_FK=post,
                        member_id_FK=member,
                        expected_amount=per_member_amount,
                        paid_amount=0,
                        status="NOT_PAID",
                    )
                )
            Contribution.objects.bulk_create(contribution_records)

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "auditor_dashboard",
                {
                    "type": "aid_post_created",
                    "post_id": post.post_id_PK,
                    "member_name": record.member_id_FK.full_name
                    if hasattr(record, "member_id_FK") and record.member_id_FK
                    else "",
                    "aid_type": table_name,
                    "total_expected": float(total_expected),
                    "target_month": post.target_month,
                },
            )
            _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})

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

        _broadcast_pending_counts()
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
                archive_transaction(v.table_name, v.record_id, officer)

            audit_entries.append(GlobalAuditTrail(
                table_name=v.table_name,
                record_id=v.record_id,
                action=action_str,
                actor_type=getattr(officer, "role", "President"),
                actor_id=officer.user_id_PK,
                actor_name=getattr(officer, "full_name", ""),
                ip_address=ip_address,
                notes=remarks.strip() if remarks else None,
            ))
            processed += 1

        if audit_entries:
            GlobalAuditTrail.objects.bulk_create(audit_entries)

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
                    active_members = Member.objects.exclude(
                        membership_status__iexact="Retired",
                    )
                    total_expected = active_members.count() * per_member_amount

                    post = AidTrackingPost.objects.create(
                        archive_id_FK=archive,
                        aid_type=v.table_name,
                        target_month=timezone.now().strftime("%Y-%m"),
                        total_expected=total_expected,
                        total_collected=0,
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

                    member_name = record.member_id_FK.full_name if record is not None and hasattr(record, "member_id_FK") and record.member_id_FK else ""
                    _broadcast_to_group("auditor_dashboard", {
                        "type": "aid_post_created",
                        "post_id": post.post_id_PK,
                        "member_name": member_name,
                        "aid_type": v.table_name,
                        "total_expected": float(total_expected),
                        "target_month": post.target_month,
                    })

            audit_entries.append(GlobalAuditTrail(
                table_name=v.table_name,
                record_id=v.record_id,
                action="APPROVED" if decision == "Approved" else "REJECTED",
                actor_type=getattr(officer, "role", "President"),
                actor_id=officer.user_id_PK,
                actor_name=getattr(officer, "full_name", ""),
                ip_address=ip_address,
                notes=remarks.strip() if remarks else None,
            ))
            processed += 1

        if audit_entries:
            GlobalAuditTrail.objects.bulk_create(audit_entries)

        _broadcast_pending_counts()
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})
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

    payment_decisions = TransactionVerification.objects.filter(
        president_id_FK__isnull=False,
    ).count()
    aid_decisions = MedicalAid.objects.filter(
        president_decided_by_user_id_FK__isnull=False,
    ).count() + DeathAid.objects.filter(
        president_decided_by_user_id_FK__isnull=False,
    ).count()
    total_approvals_count = payment_decisions + aid_decisions

    return JsonResponse({
        "ok": True,
        "verified_dues_count": verified_dues_count,
        "verified_claims_count": verified_claims_count,
        "total_approvals_count": total_approvals_count,
    })
