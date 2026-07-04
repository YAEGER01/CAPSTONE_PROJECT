import decimal
import hashlib
import json
import re
from datetime import datetime
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core_system.api_utils import member_to_json
from core_system.guards import require_role
from core_system.models import (
    Member,
    MembershipFee,
    OfficerUser,
    MonthlyDues,
    TransactionVerification,
    MedicalAid,
    DeathAid,
    Claimant,
    SupportingProof,
    FinancialDocumentArchive,
    AuditFindingsReport,
    TransactionArchive,
    GlobalAuditTrail,
)
from core_system.constants.policy_constants import (
    check_medical_aid_once_per_year,
    get_accidental_sickness_aid_benefit,
    get_accidental_sickness_aid_threshold,
    get_death_aid_amount,
    get_expected_dues_amount,
    get_membership_fee_amount,
    get_monthly_dues_amount,
    is_exempt_from_dues_and_aid,
)
from core_system.shared_view_utils import (
    MODEL_MAP,
    UPDATABLE_FIELDS,
    MONTH_COVERED_PATTERN,
    PAYMENT_ENTITY_TYPE_LABELS,
    normalize_month_covered,
    get_request_month_covered,
    resolve_officer_from_session,
    resolve_member_from_input,
    check_member_not_retired,
    _get_rejection_info,
    _get_encoder_name,
    _get_proof_url,
    _sha256_of_uploaded_file,
    _compute_row_signature,
    _link_proof_to_record,
    _audit_evidence_filename,
    _get_auditor_finding_evidence,
    _get_auditor_verification_remarks,
    _serialize_value,
    _serialize_for_audit,
    _record_audit_trail,
    archive_transaction,
    _broadcast_pending_counts,
)
from django.core.files.storage import default_storage
from django.http import HttpRequest


# ==========================================================================
# TREASURER WORKSPACE VIEWS
# ==========================================================================

def _broadcast_treasurer(section: str) -> None:
    try:
        async_to_sync(get_channel_layer().group_send)(
            "treasurer_dashboard",
            {"type": "data_changed", "section": section},
        )
    except Exception:
        pass


def treasurer_dashboard(request):
    """Loads the unified Treasurer/Auditor executive workspace page."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    # Header identity: Ambassador Green = logged-in officer full_name (fallback: role: treasurer).
    officer_full_name = ""
    officer_role = "treasurer"

    # Project uses a custom officer session (see auth_views.py). request.user may not be set.
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
        "expected_dues_default_amount": get_expected_dues_amount(),
    }

    # If full_name missing/empty: use the fallback as required by the spec.
    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    context["returned_entries_count"] = TransactionVerification.objects.filter(
        table_name="membership_fee",
        verification_status="Returned for Revision",
    ).count()

    context["monthly_dues_returned_count"] = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status="Returned for Revision",
    ).count()

    context["medical_aid_returned_count"] = TransactionVerification.objects.filter(
        table_name="medical_aid",
        verification_status="Returned for Revision",
    ).count()

    context["death_aid_returned_count"] = TransactionVerification.objects.filter(
        table_name="death_aid",
        verification_status="Returned for Revision",
    ).count()

    return render(request, "website/Treasurer/treasurer_dashboard.html", context)


# --- Member Enrollment / Listing APIs (Treasurer) ---
@require_POST
def treasurer_add_member(request: HttpRequest):
    """
    Enroll a new MEMBER row and conditionally process an initial membership fee ledger
    record synchronously within a single atomic database context payload window.
    """
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    # Extract Core Member Variables
    prof_name = (request.POST.get("prof_name") or "").strip()
    prof_id = (request.POST.get("prof_id") or "").strip()
    prof_contact = (request.POST.get("prof_contact") or "").strip() or None
    prof_email = (request.POST.get("prof_email") or "").strip() or None
    prof_status = (request.POST.get("prof_status") or "Active").strip()
    prof_dept = (request.POST.get("prof_dept") or "").strip()
    prof_pos = (request.POST.get("prof_pos") or "").strip()

    # Validations: Member
    if not prof_name:
        return JsonResponse({"ok": False, "error": "Full Legal Name is required."}, status=400)
    if not prof_id:
        return JsonResponse({"ok": False, "error": "Employee/Faculty ID is required."}, status=400)

    employee_id_max_length = Member._meta.get_field("employee_id").max_length
    if len(prof_id) > employee_id_max_length:
        return JsonResponse(
            {"ok": False, "error": f"Employee/Faculty ID must be {employee_id_max_length} characters or fewer."},
            status=400,
        )

    if prof_email and "@" not in prof_email:
        return JsonResponse({"ok": False, "error": "Institutional Email looks invalid."}, status=400)

    # Resolve Encoder User Identity context
    recorded_by = resolve_officer_from_session(request)

    # Parse Visibility Interface Control Flags
    payment_required = request.POST.get("payment_required") == "true"
    receipt_required = request.POST.get("receipt_required") == "true"

    # Enforce transactional data integrity checks across models
    try:
        with transaction.atomic():
            # 1. Store Profile Attachments safely if provided
            prof_uploaded = request.FILES.get("prof_photo_file")
            if prof_uploaded and prof_uploaded.size > 0:
                default_storage.save(
                    f"member_uploads/{timezone.now().strftime('%Y%m%d')}_{prof_uploaded.name}",
                    prof_uploaded,
                )

            # 2. Provision Member Record Block
            member = Member.objects.create(
                full_name=prof_name,
                employee_id=prof_id,
                department=prof_dept or None,
                position=prof_pos or None,
                contact_number=prof_contact,
                email=prof_email,
                employment_status=prof_status,
                membership_status=prof_status,
                member_type=prof_id,
                date_joined=timezone.now().date(),
            )

            # 3. Handle Conditional Onboarding Payment Logic
            if payment_required:
                fee_method = (request.POST.get("fee_method") or "").strip()
                fee_date = (request.POST.get("fee_date") or "").strip()
                fee_amount_raw = (request.POST.get("fee_amount") or "500.00").strip()

                if not fee_method:
                    raise ValueError("Payment method is required when logging a profile payment entry.")
                if not fee_date:
                    raise ValueError("Payment Date is required when logging a profile payment entry.")

                try:
                    amount_decimal = decimal.Decimal(fee_amount_raw)
                    if amount_decimal <= 0:
                        raise ValueError()
                except (decimal.InvalidOperation, ValueError):
                    raise ValueError("Payment Amount must be a positive valid numeric description.")

                # Defaulting verification properties explicitly to onboarding configuration norms
                fee_status = "Full Payment"
                fee_month = "ONBOARDING"  # Clean fallback string to signal initialization fee

                # Base Setup for Audit Logs
                fee_ref = None
                fee_encoder = None

                # 4. Handle Conditional Receipt Verification Sub-Logic
                if receipt_required:
                    fee_ref = (request.POST.get("fee_ref") or "").strip()
                    fee_encoder = (request.POST.get("fee_encoder") or "").strip()
                    fee_uploaded = request.FILES.get("fee_photo_file")

                    if not fee_ref:
                        raise ValueError("Receipt / Reference Number is required when audit tracking is checked.")
                    if not fee_encoder:
                        raise ValueError("Encoded By description tag identity is required when audit tracking is checked.")
                    if not fee_uploaded or fee_uploaded.size == 0:
                        raise ValueError("An official photo proof attachment of the receipt file must be uploaded.")

                # If receipt check is omitted entirely, resolve session context dynamically for fallback values
                if not fee_encoder and recorded_by:
                    fee_encoder = recorded_by.full_name or "System Automatic Encoder"

                # 5. Provision MembershipFee Database Entry Row
                fee = MembershipFee.objects.create(
                    member_id_FK=member,
                    receipt_number=fee_ref or f"SYS-TEMP-{int(timezone.now().timestamp())}",
                    amount=str(amount_decimal),
                    month_covered=fee_month,
                    payment_date=fee_date,
                    payment_method=fee_method,
                    payment_status=fee_status,
                    deposit_reference=fee_encoder or None,
                    recorded_by_user_id_FK=recorded_by,
                )

                # 6. Initialize verification records
                TransactionVerification.objects.create(
                    table_name="membership_fee",
                    record_id=fee.fee_id_PK,
                    verification_status="Pending",
                )

                # Link document files securely via your internal system hooks
                if receipt_required and fee_uploaded:
                    _link_proof_to_record(fee_uploaded, fee, recorded_by)

                # Write record properties into historical audit trail hooks
                _record_audit_trail(
                    table="membership_fee",
                    record_id=fee.fee_id_PK,
                    action="CREATED",
                    actor=recorded_by,
                    new={
                        "member": member,
                        "receipt_number": fee.receipt_number,
                        "amount": str(amount_decimal),
                        "month_covered": fee_month,
                        "payment_date": fee_date,
                        "payment_method": fee_method,
                        "payment_status": fee_status,
                        "deposit_reference": fee_encoder,
                    },
                    ip=request.META.get("REMOTE_ADDR"),
                )

    except ValueError as val_err:
        # Atomic block gracefully triggers a database rollback on explicit error raises
        return JsonResponse({"ok": False, "error": str(val_err)}, status=400)
    except Exception as ex:
        return JsonResponse({"ok": False, "error": f"Internal pipeline transactional exception: {str(ex)}"}, status=500)

    _broadcast_treasurer("members")

    return JsonResponse(
        {
            "ok": True,
            "member": {
                "member_id": member.member_id_PK,
                "full_name": member.full_name,
                "employee_id": member.employee_id or "",
                "department": member.department or "",
                "position": member.position or "",
                "contact_number": member.contact_number,
                "email": member.email,
                "membership_status": member.membership_status,
                "employment_status": member.employment_status,
                "member_type": member.member_type or member.employee_id,
                "date_joined": str(member.date_joined),
            }
        }
    )
@require_GET
def treasurer_membership_fee_list(request):
    """Return all membership fee ledger entries for the Treasurer dashboard."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    fees = (
        MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
        .all()
        .order_by("-fee_id_PK")
    )

    # OfficerUser model does not guarantee a display name, so we return recorded_by_user_id_FK_id as fallback.
    rows = []
    for f in fees:
        encoder_name = None
        if getattr(f, "recorded_by_user_id_FK", None) is not None:
            encoder_name = getattr(f.recorded_by_user_id_FK, "full_name", None)
            if not encoder_name:
                encoder_name = str(getattr(f.recorded_by_user_id_FK, "user_id_PK", f.recorded_by_user_id_FK_id))

        rows.append(
            {
                "fee_id": f.fee_id_PK,
                "ref": f.receipt_number or "",
                "member_id": f.member_id_FK.member_id_PK,
                "member_name": f.member_id_FK.full_name,
                "amount": str(f.amount),
                "month_covered": f.month_covered or "",
                "payment_date": str(f.payment_date),
                "payment_status": f.payment_status,
                "payment_method": f.payment_method,
                "deposit_reference": f.deposit_reference,
                "encoded_by": encoder_name or "",
            }
        )

    return JsonResponse({"ok": True, "fees": rows})


@require_GET
def treasurer_membership_fees_returned_list(request):
    """Return membership fee records that have been returned for revision."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="membership_fee",
        verification_status="Returned for Revision"
    )

    rows = []
    for tv in returned_verifications:
        try:
            fee = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").get(
                fee_id_PK=tv.record_id
            )
        except MembershipFee.DoesNotExist:
            continue

        rejection_reason, rejection_details = _get_rejection_info("membership_fee", fee.fee_id_PK)
        encoder_name = _get_encoder_name(fee)
        proof_url = _get_proof_url(MembershipFee, fee.fee_id_PK)

        rows.append({
            "fee_id_PK": fee.fee_id_PK,
            "receipt_number": fee.receipt_number or "",
            "member_id_PK": fee.member_id_FK.member_id_PK,
            "member_name": fee.member_id_FK.full_name,
            "amount": str(fee.amount),
            "month_covered": fee.month_covered or "",
            "payment_date": str(fee.payment_date),
            "payment_status": fee.payment_status,
            "payment_method": fee.payment_method,
            "deposit_reference": fee.deposit_reference,
            "encoded_by": encoder_name or "",
            "partial_amount": str(getattr(fee, "partial_amount", "") or ""),
            "rejection_reason": rejection_reason,
            "rejection_details": rejection_details,
            "proof_url": proof_url or "",
        })

    return JsonResponse({"ok": True, "records": rows})


@require_GET
def treasurer_monthly_dues_returned_list(request):
    """Return monthly dues records (OTC and Salary Deduction) that have been returned for revision."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status="Returned for Revision"
    )

    rows = []
    for tv in returned_verifications:
        try:
            dues = MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK").get(
                dues_id_PK=tv.record_id
            )
        except MonthlyDues.DoesNotExist:
            continue

        rejection_reason, rejection_details = _get_rejection_info("monthly_dues", dues.dues_id_PK)
        encoder_name = _get_encoder_name(dues)
        proof_url = _get_proof_url(MonthlyDues, dues.dues_id_PK)

        rows.append({
            "dues_id_PK": dues.dues_id_PK,
            "receipt_number": dues.receipt_number or "",
            "member_id_PK": dues.member_id_FK.member_id_PK,
            "member_name": dues.member_id_FK.full_name,
            "amount": str(dues.amount),
            "month_covered": dues.month_covered or "",
            "payment_date": str(dues.payment_date),
            "payment_status": dues.payment_status,
            "payment_method": dues.payment_method,
            "remittance_reference": dues.remittance_reference or "",
            "deduction_batch_reference": dues.deduction_batch_reference or "",
            "encoded_by": encoder_name or "",
            "rejection_reason": rejection_reason,
            "rejection_details": rejection_details,
            "proof_url": proof_url or "",
        })

    return JsonResponse({"ok": True, "records": rows})


@require_GET
def treasurer_medical_aid_returned_list(request):
    """Return medical aid records that have been returned for revision."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="medical_aid",
        verification_status="Returned for Revision"
    )

    rows = []
    for tv_rec in returned_verifications:
        try:
            aid = MedicalAid.objects.select_related("member_id_FK").get(
                medical_aid_id_PK=tv_rec.record_id
            )
        except MedicalAid.DoesNotExist:
            continue

        rejection_reason, rejection_details = _get_rejection_info("medical_aid", aid.medical_aid_id_PK)
        proof_url = _get_proof_url(MedicalAid, aid.medical_aid_id_PK)

        rows.append({
            "record_id": aid.medical_aid_id_PK,
            "display_id": f"MED-{aid.medical_aid_id_PK}",
            "member_id_PK": aid.member_id_FK.member_id_PK,
            "member_name": aid.member_id_FK.full_name,
            "request_date": str(aid.request_date),
            "requested_amount": str(aid.requested_amount or ""),
            "hospital_name": aid.hospital_name or "",
            "hospital_bill_amount": str(aid.hospital_bill_amount),
            "claim_year": str(aid.claim_year),
            "document_status": aid.document_status or "",
            "status": aid.status or "",
            "validated_aid_amount": str(aid.validated_aid_amount),
            "rejection_reason": rejection_reason,
            "rejection_details": rejection_details,
            "proof_url": proof_url or "",
        })

    return JsonResponse({"ok": True, "records": rows})


@require_GET
def treasurer_death_aid_returned_list(request):
    """Return death aid records that have been returned for revision."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="death_aid",
        verification_status="Returned for Revision"
    )

    rows = []
    for tv_rec in returned_verifications:
        try:
            aid = DeathAid.objects.select_related("member_id_FK", "claimant_id_FK").get(
                death_aid_id_PK=tv_rec.record_id
            )
        except DeathAid.DoesNotExist:
            continue

        rejection_reason, rejection_details = _get_rejection_info("death_aid", aid.death_aid_id_PK)
        proof_url = _get_proof_url(DeathAid, aid.death_aid_id_PK)

        rows.append({
            "record_id": aid.death_aid_id_PK,
            "display_id": f"DTH-{aid.death_aid_id_PK}",
            "member_id_PK": aid.member_id_FK.member_id_PK,
            "member_name": aid.member_id_FK.full_name,
            "claimant_name": aid.claimant_id_FK.full_name if aid.claimant_id_FK else "",
            "claim_date": str(aid.claim_date),
            "claim_type": aid.claim_type or "",
            "deceased_name": aid.deceased_name or "",
            "relationship_to_member": aid.relationship_to_member or "",
            "benefit_amount": str(aid.benefit_amount),
            "bill_amount": str(aid.bill_amount) if aid.bill_amount else "",
            "document_status": aid.document_status or "",
            "status": aid.status or "",
            "rejection_reason": rejection_reason,
            "rejection_details": rejection_details,
            "proof_url": proof_url or "",
        })

    return JsonResponse({"ok": True, "records": rows})


@require_GET
def treasurer_approved_transactions_total(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    qs = TransactionArchive.objects.filter(
        status="Approved",
        transaction_type__in=["membership_fee", "monthly_dues"],
    ).select_related()

    total = sum(float(entry.amount or 0) for entry in qs)

    return JsonResponse({"ok": True, "total": total})

    

    
#new_membership_add
@require_POST
def treasurer_membership_fee_add(request: HttpRequest):
    """Create a MEMBERSHIP_FEE row from the Treasurer membership fee form."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    from core_system.services.membership_fee_rules import (
        check_membership_fee_requirement,
        validate_membership_fee_payment,
    )

    fee_member = (request.POST.get("fee_member") or "").strip()
    fee_method = (request.POST.get("fee_method") or "").strip()
    fee_status = (request.POST.get("fee_status") or "").strip()
    fee_date = (request.POST.get("fee_date") or "").strip()
    fee_month = normalize_month_covered(get_request_month_covered(request))
    fee_ref = (request.POST.get("fee_ref") or "").strip()
    fee_encoder = (request.POST.get("fee_encoder") or "").strip()

    if not fee_member:
        return JsonResponse({"ok": False, "error": "Associated Member ID is required."}, status=400)
    if not fee_method:
        return JsonResponse({"ok": False, "error": "Payment method is required."}, status=400)
    if not fee_status:
        fee_status = "Full Payment"
    if fee_status not in ("Full Payment", "Partial"):
        return JsonResponse({"ok": False, "error": "Payment status must be Full Payment or Partial."}, status=400)
    if not fee_date:
        return JsonResponse({"ok": False, "error": "Payment Date is required."}, status=400)
    if not fee_month:
        return JsonResponse({"ok": False, "error": "Deduction Month / Covered Period is required."}, status=400)
        
    # ─── UPDATED BI-PASS FOR REGISTRATION FEES ───
    if fee_month != "Registration Fee":
        if not MONTH_COVERED_PATTERN.match(fee_month):
            return JsonResponse({"ok": False, "error": "Deduction Month / Covered Period must use YYYY-MM."}, status=400)

    month_covered_max_length = MembershipFee._meta.get_field("month_covered").max_length
    
    if len(fee_month) > month_covered_max_length:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Deduction Month / Covered Period must be {month_covered_max_length} characters or fewer.",
            },
            status=400,
        )
    if not fee_ref:
        return JsonResponse({"ok": False, "error": "Receipt / Reference Number is required."}, status=400)

    member_obj, err = resolve_member_from_input(fee_member)
    if err:
        return err

    if is_exempt_from_dues_and_aid(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from monthly dues per ARTICLE XI Section 2."},
            status=400,
        )

    # Resolve officer session for potential exceptions and workflows
    recorded_by = resolve_officer_from_session(request)
    
    # Check policy requirement
    required_check = check_membership_fee_requirement(member_obj)
    if not required_check.required_to_pay:
        if recorded_by is not None:
            from core_system.services.membership_fee_rules import (
                record_membership_fee_policy_exception,
            )
            record_membership_fee_policy_exception(
                member=member_obj,
                reason=required_check.exception_reason or "Fee not required.",
                officer=recorded_by,
                request=request,
            )

        return JsonResponse(
            {
                "ok": False,
                "error": "Membership fee policy exception",
                "reason": required_check.exception_reason or "Fee not required.",
            },
            status=400,
        )

    validation = validate_membership_fee_payment(
        payload={
            "fee_status": fee_status,
            "fee_ref": fee_ref,
            "fee_amount": request.POST.get("fee_amount"),
            "fee_partial_amount": request.POST.get("fee_partial_amount"),
        }
    )

    if not validation.valid:
        from core_system.services.membership_fee_rules import (
            create_correction_artifacts_for_membership_fee,
        )
        from core_system.services.notifications import (
            notify_membership_fee_correction_required,
        )

        if recorded_by is None:
            return JsonResponse(
                {"ok": False, "error": "Unable to resolve officer session for encoding."},
                status=401,
            )

        amount_value = str((validation.normalized.get("fee_amount")))

        with transaction.atomic():
            fee = MembershipFee.objects.create(
                member_id_FK=member_obj,
                receipt_number=fee_ref,
                amount=amount_value,
                month_covered=fee_month,
                payment_date=fee_date,
                payment_method=fee_method,
                payment_status=fee_status,
                deposit_reference=fee_encoder or None,
                recorded_by_user_id_FK=recorded_by,
            )

            TransactionVerification.objects.create(
                table_name="membership_fee",
                record_id=fee.fee_id_PK,
                verification_status="Returned for Revision",
            )

            create_correction_artifacts_for_membership_fee(
                fee=fee,
                officer=recorded_by,
                validation_errors=validation.errors,
                request=request,
            )

        notify_membership_fee_correction_required(member=member_obj)

        return JsonResponse(
            {
                "ok": False,
                "error": "Payment requires correction",
                "errors": validation.errors,
                "fee_id": fee.fee_id_PK,
            },
            status=400,
        )

    amount_value = str(validation.normalized.get("fee_amount"))

    if recorded_by is None:
        return JsonResponse({"ok": False, "error": "Unable to resolve officer session for encoding."}, status=401)

    from core_system.services.membership_fee_rules import (
        has_duplicate_membership_fee,
    )
    from core_system.services.notifications import (
        notify_membership_fee_policy_exception,
        notify_membership_fee_correction_required,
        notify_membership_fee_confirmed,
    )

    dup_check = has_duplicate_membership_fee(
        member=member_obj,
        receipt_number=fee_ref,
    )
    if dup_check.is_duplicate:
        return JsonResponse(
            {
                "ok": False,
                "error": "Duplicate fee entry detected for this member and receipt number.",
                "existing_fee_id": dup_check.existing_fee_id,
            },
            status=400,
        )

    uploaded = request.FILES.get("fee_photo_file")

    with transaction.atomic():
        fee = MembershipFee.objects.create(
            member_id_FK=member_obj,
            receipt_number=fee_ref,
            amount=amount_value,
            month_covered=fee_month,
            payment_date=fee_date,
            payment_method=fee_method,
            payment_status=fee_status,
            deposit_reference=fee_encoder or None,
            recorded_by_user_id_FK=recorded_by,
        )

        TransactionVerification.objects.create(
            table_name="membership_fee",
            record_id=fee.fee_id_PK,
            verification_status="Pending",
        )

        if uploaded and uploaded.size > 0:
            _link_proof_to_record(uploaded, fee, recorded_by)

        _record_audit_trail(
            table="membership_fee",
            record_id=fee.fee_id_PK,
            action="CREATED",
            actor=recorded_by,
            new={
                "member": member_obj,
                "receipt_number": fee_ref,
                "amount": amount_value,
                "month_covered": fee_month,
                "payment_date": fee_date,
                "payment_method": fee_method,
                "payment_status": fee_status,
                "deposit_reference": fee_encoder or None,
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

    _broadcast_treasurer("membership_fees")

    return JsonResponse(
        {
            "ok": True,
            "fee": {
                "fee_id": fee.fee_id_PK,
                "member_id": member_obj.member_id_PK,
                "member_name": member_obj.full_name,
                "amount": str(fee.amount),
                "month_covered": fee.month_covered or "",
                "payment_date": str(fee.payment_date),
                "payment_status": fee.payment_status,
                "payment_method": fee.payment_method,
                "ref": fee.receipt_number,
                "encoded_by": recorded_by.full_name,
                "proof_attached": bool(uploaded and uploaded.size > 0),
            },
        }
    )

#end_new_


def _process_monthly_dues_entry(request, payment_type, **kwargs):
    """Shared monthly dues creation logic for OTC and Salary Deduction.

    kwargs must contain:
      member_input, month_raw, amount_raw
    OTC: date_raw, method, ref, uploaded
    Salary: summary, sal_ref, uploaded
    """
    member_input = kwargs.get("member_input", "").strip()
    month_raw = kwargs.get("month_raw", "").strip()
    amount_raw = kwargs.get("amount_raw", "").strip()

    if not member_input:
        return JsonResponse({"ok": False, "error": "Associated Member ID is required."}, status=400)
    if not month_raw:
        return JsonResponse({"ok": False, "error": "Month Covered is required."}, status=400)
    if not amount_raw:
        return JsonResponse({"ok": False, "error": "Amount Paid is required."}, status=400)

    month = normalize_month_covered(month_raw)

    try:
        amount_decimal = decimal.Decimal(amount_raw)
    except decimal.InvalidOperation:
        return JsonResponse({"ok": False, "error": "Amount must be a valid number."}, status=400)

    if amount_decimal <= 0:
        return JsonResponse({"ok": False, "error": "Amount must be positive."}, status=400)

    expected = decimal.Decimal(str(get_monthly_dues_amount()))
    if abs(amount_decimal - expected) > decimal.Decimal("0.01"):
        return JsonResponse(
            {"ok": False, "error": f"Monthly dues amount must be exactly ₱{expected:.2f} per ARTICLE XI Section 1.c."},
            status=400,
        )

    member, err = resolve_member_from_input(member_input)
    if err:
        return err

    ret = check_member_not_retired(member)
    if ret:
        return ret

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Unable to resolve officer session for encoding."}, status=401)

    if payment_type == "otc":
        date_raw = kwargs.get("date_raw", "").strip()
        method = kwargs.get("method", "").strip() or "Unknown"
        ref = kwargs.get("ref", "").strip()
        uploaded = kwargs.get("uploaded")

        if not date_raw:
            return JsonResponse({"ok": False, "error": "Payment Date is required."}, status=400)
        if not ref:
            return JsonResponse({"ok": False, "error": "Receipt / Reference Number is required."}, status=400)

        with transaction.atomic():
            dues = MonthlyDues.objects.create(
                member_id_FK=member,
                month_covered=month,
                amount=str(amount_decimal),
                payment_method=method,
                payment_status="Paid",
                payment_date=date_raw,
                receipt_number=ref,
                recorded_by_user_id_FK=officer,
            )
            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending",
            )
            if uploaded and getattr(uploaded, "size", 0) > 0:
                _link_proof_to_record(uploaded, dues, officer)
            _record_audit_trail(
                table="monthly_dues",
                record_id=dues.dues_id_PK,
                action="CREATED",
                actor=officer,
                new={"member": member, "month_covered": month, "amount": str(amount_decimal),
                     "payment_method": method, "payment_date": date_raw, "receipt_number": ref},
                ip=request.META.get("REMOTE_ADDR"),
            )
        _broadcast_treasurer("monthly_dues")
        return JsonResponse({"ok": True, "dues": {
            "dues_id": dues.dues_id_PK,
            "ref": dues.receipt_number or "",
            "member_id": member.member_id_PK,
            "member_name": member.full_name,
            "month": dues.month_covered,
            "amount": str(dues.amount),
            "method": dues.payment_method,
            "date": str(dues.payment_date),
            "proof_attached": bool(uploaded and getattr(uploaded, "size", 0) > 0),
        }})

    else:  # salary
        summary = kwargs.get("summary", "").strip()
        sal_ref = kwargs.get("sal_ref", "").strip()
        uploaded = kwargs.get("uploaded")

        if not summary:
            return JsonResponse({"ok": False, "error": "Accounting Deduction Summary Remarks are required."}, status=400)
        if not sal_ref:
            return JsonResponse({"ok": False, "error": "Remittance Reference Number is required."}, status=400)

        try:
            payment_date = datetime.strptime(month + "-01", "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid deduction month format."}, status=400)

        with transaction.atomic():
            dues = MonthlyDues.objects.create(
                member_id_FK=member,
                month_covered=month,
                amount=str(amount_decimal),
                payment_method="Salary Deduction",
                payment_status="Paid",
                payment_date=payment_date,
                deduction_batch_reference=summary,
                remittance_reference=sal_ref,
                recorded_by_user_id_FK=officer,
            )
            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending",
            )
            if uploaded and getattr(uploaded, "size", 0) > 0:
                _link_proof_to_record(uploaded, dues, officer)
            _record_audit_trail(
                table="monthly_dues",
                record_id=dues.dues_id_PK,
                action="CREATED",
                actor=officer,
                new={"member": member, "month_covered": month, "amount": str(amount_decimal),
                     "payment_method": "Salary Deduction", "payment_date": str(payment_date),
                     "deduction_batch_reference": summary, "remittance_reference": sal_ref},
                ip=request.META.get("REMOTE_ADDR"),
            )
        _broadcast_treasurer("monthly_dues")
        return JsonResponse({"ok": True, "dues": {
            "dues_id": dues.dues_id_PK,
            "ref": dues.remittance_reference or "",
            "member_id": member.member_id_PK,
            "member_name": member.full_name,
            "month": dues.month_covered,
            "amount": str(dues.amount),
            "remarks": dues.deduction_batch_reference or "",
        }})


@require_POST
def treasurer_monthly_dues_add(request: HttpRequest):
    """Unified monthly dues add view. Supports both 'otc' and 'salary' payment_type."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    payment_type = (request.POST.get("payment_type") or "").strip().lower()
    if not payment_type:
        if "otc_member" in request.POST or "otc_ref" in request.POST:
            payment_type = "otc"
        elif "sal_member" in request.POST or "sal_ref" in request.POST:
            payment_type = "salary"
        else:
            return JsonResponse({"ok": False, "error": "payment_type must be 'otc' or 'salary'."}, status=400)

    if payment_type == "otc":
        return _process_monthly_dues_entry(request, "otc",
            member_input=request.POST.get("otc_member") or request.POST.get("member") or "",
            month_raw=request.POST.get("otc_month") or request.POST.get("month") or "",
            amount_raw=request.POST.get("otc_amount") or request.POST.get("amount") or "",
            date_raw=request.POST.get("otc_date") or request.POST.get("date") or "",
            method=request.POST.get("otc_method") or request.POST.get("method") or "",
            ref=request.POST.get("otc_ref") or request.POST.get("ref") or "",
            uploaded=request.FILES.get("otc_photo_file") or request.FILES.get("photo_file"),
        )
    else:
        return _process_monthly_dues_entry(request, "salary",
            member_input=request.POST.get("sal_member") or request.POST.get("member") or "",
            month_raw=request.POST.get("sal_month") or request.POST.get("month") or "",
            amount_raw=request.POST.get("sal_amount") or request.POST.get("amount") or "",
            summary=request.POST.get("sal_summary") or request.POST.get("summary") or "",
            sal_ref=request.POST.get("sal_ref") or request.POST.get("remittance_ref") or "",
            uploaded=request.FILES.get("sal_photo_file") or request.FILES.get("photo_file"),
        )


@require_POST
def treasurer_monthly_dues_otc_add(request: HttpRequest):
    """Legacy OTC add wrapper — delegates to unified view."""
    return treasurer_monthly_dues_add(request)


def treasurer_monthly_dues_otc_list(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    dues = (
        MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
        .filter(payment_method__in=["Cash OTC", "GCash QR", "Cashier Handover"])
        .order_by("-dues_id_PK")
    )

    rows = []
    for d in dues:
        rows.append(
            {
                "dues_id": d.dues_id_PK,
                "ref": d.receipt_number or "",
                "member_id": d.member_id_FK.member_id_PK,
                "member_name": d.member_id_FK.full_name,
                "month": d.month_covered,
                "amount": str(d.amount),
                "method": d.payment_method,
                "date": str(d.payment_date) if d.payment_date else "",
                "payment_status": d.payment_status,
            }
        )

    return JsonResponse({"ok": True, "otc_dues": rows})


@require_POST
def treasurer_monthly_dues_salary_add(request: HttpRequest):
    """Legacy Salary Deduction add wrapper — delegates to unified view."""
    return treasurer_monthly_dues_add(request)


@require_GET
def treasurer_monthly_dues_salary_list(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    dues = (
        MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
        .filter(payment_method="Salary Deduction")
        .order_by("-dues_id_PK")
    )

    rows = []
    batches_map = {}
    for d in dues:
        rows.append(
            {
                "dues_id": d.dues_id_PK,
                "ref": d.remittance_reference or "",
                "member_id": d.member_id_FK.member_id_PK,
                "member_name": d.member_id_FK.full_name,
                "month": d.month_covered,
                "amount": str(d.amount),
                "remarks": d.deduction_batch_reference or "",
            }
        )

        br = (d.deduction_batch_reference or "").strip()
        if not br:
            continue
        if br not in batches_map:
            batches_map[br] = {
                "batch_reference": br,
                "month": d.month_covered,
                "member_count": 0,
                "total_amount": 0.0,
                "members": [],
            }
        batches_map[br]["member_count"] += 1
        batches_map[br]["total_amount"] += float(d.amount)
        batches_map[br]["members"].append({
            "dues_id": d.dues_id_PK,
            "member_id": d.member_id_FK.member_id_PK,
            "member_name": d.member_id_FK.full_name,
            "amount": str(d.amount),
        })

    return JsonResponse({
        "ok": True,
        "salary_dues": rows,
        "batches": list(batches_map.values()),
    })


@require_POST
def treasurer_salary_bulk_preview(request: HttpRequest):
    """Preview active members for bulk salary deduction processing."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    sal_month = (request.POST.get("sal_month") or "").strip()
    if not sal_month:
        return JsonResponse({"ok": False, "error": "sal_month is required."}, status=400)

    expected_amount = get_monthly_dues_amount()

    active_members = Member.objects.exclude(membership_status__iexact="retired").order_by("full_name")

    existing = set(
        MonthlyDues.objects.filter(
            payment_method="Salary Deduction",
            month_covered=sal_month,
            member_id_FK__in=active_members.values_list("member_id_PK", flat=True),
        ).values_list("member_id_FK", flat=True)
    )

    members = []
    for m in active_members:
        already = m.member_id_PK in existing
        members.append({
            "member_id": m.member_id_PK,
            "member_name": m.full_name,
            "department": m.department or "",
            "status": m.membership_status,
            "already_exists": already,
            "default_checked": not already,
        })

    return JsonResponse({
        "ok": True,
        "month": sal_month,
        "expected_amount": float(expected_amount),
        "members": members,
        "total_active": active_members.count(),
        "already_processed": len(existing),
    })


@require_POST
def treasurer_salary_bulk_process(request: HttpRequest):
    """Create salary deduction records for multiple members in one batch."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    sal_month = (request.POST.get("sal_month") or "").strip()
    batch_ref = (request.POST.get("batch_ref") or "").strip()
    summary = (request.POST.get("summary") or "").strip()
    member_ids_raw = (request.POST.get("member_ids") or "").strip()
    uploaded = request.FILES.get("sal_photo_file")

    if not sal_month:
        return JsonResponse({"ok": False, "error": "sal_month is required."}, status=400)
    if not batch_ref:
        return JsonResponse({"ok": False, "error": "batch_ref is required."}, status=400)
    if not member_ids_raw:
        return JsonResponse({"ok": False, "error": "member_ids is required."}, status=400)

    try:
        member_ids = json.loads(member_ids_raw)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "member_ids must be a JSON array."}, status=400)

    if not isinstance(member_ids, list) or not member_ids:
        return JsonResponse({"ok": False, "error": "member_ids must be a non-empty array."}, status=400)

    expected_amount = get_monthly_dues_amount()

    try:
        payment_date = datetime.strptime(sal_month + "-01", "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid month format."}, status=400)

    # Deduplicate member_ids
    unique_ids = list(set(member_ids))

    # Fetch members and existing records in bulk
    members_map = {
        m.member_id_PK: m
        for m in Member.objects.filter(member_id_PK__in=unique_ids)
    }
    existing_for_month = set(
        MonthlyDues.objects.filter(
            payment_method="Salary Deduction",
            month_covered=sal_month,
            member_id_FK__in=unique_ids,
        ).values_list("member_id_FK", flat=True)
    )

    processed = 0
    skipped = 0
    created_dues = []

    with transaction.atomic():
        for mid in unique_ids:
            member = members_map.get(mid)
            if not member:
                skipped += 1
                continue
            if str(member.membership_status) == "retired":
                skipped += 1
                continue
            if mid in existing_for_month:
                skipped += 1
                continue

            dues = MonthlyDues.objects.create(
                member_id_FK=member,
                month_covered=sal_month,
                amount=str(expected_amount),
                payment_method="Salary Deduction",
                payment_status="Paid",
                payment_date=payment_date,
                deduction_batch_reference=summary,
                remittance_reference=batch_ref,
                recorded_by_user_id_FK=officer,
            )
            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending",
            )
            if uploaded and getattr(uploaded, "size", 0) > 0:
                _link_proof_to_record(uploaded, dues, officer)

            _record_audit_trail(
                table="monthly_dues",
                record_id=dues.dues_id_PK,
                action="CREATED",
                actor=officer,
                new={
                    "member": getattr(member, "full_name", str(mid)),
                    "month_covered": sal_month,
                    "amount": str(expected_amount),
                    "payment_method": "Salary Deduction",
                    "batch_ref": batch_ref,
                },
                ip=request.META.get("REMOTE_ADDR"),
            )
            processed += 1
            created_dues.append(dues.dues_id_PK)

    _broadcast_pending_counts()
    return JsonResponse({
        "ok": True,
        "processed": processed,
        "skipped": skipped,
        "batch_ref": batch_ref,
        "month": sal_month,
    })


@require_GET
def treasurer_medical_aid_list(request: HttpRequest):
    """Return MedicalAid records for the Treasurer dashboard table."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    aids = (
        MedicalAid.objects.select_related("member_id_FK")
        .order_by("-medical_aid_id_PK")
    )

    rows = []
    for aid in aids:
        requested_amount = aid.requested_amount or aid.hospital_bill_amount
        rows.append(
            {
                "id": f"MED-{aid.medical_aid_id_PK}",
                "memberId": aid.member_id_FK.member_id_PK,
                "name": aid.member_id_FK.full_name,
                "date": aid.request_date.isoformat(),
                "reason": aid.status or "Medical Aid Request",
                "reqAmount": float(requested_amount),
                "hospital": aid.hospital_name or aid.member_id_FK.full_name,
                "bill": float(aid.hospital_bill_amount),
                "validation": aid.status or "Pending",
                "status": aid.status or "Pending",
            }
        )

    return JsonResponse({"ok": True, "medical_aids": rows})


@require_GET
def treasurer_releases_list(request: HttpRequest):
    """Return released transactions from the archive."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    qs = TransactionArchive.objects.filter(
        status="Released",
        transaction_type__in=["medical_aid", "death_aid"],
    ).select_related(
        "released_by_user_id_FK",
    ).order_by("-archive_id_PK")

    releases = []
    for entry in qs:
        released_by = (
            getattr(entry.released_by_user_id_FK, "full_name", "") or ""
        )
        aid_type = "Medical Aid" if entry.transaction_type == "medical_aid" else "Death Aid"
        releases.append(
            {
                "id": f"REL-{entry.archive_id_PK}",
                "aidId": f"{'MED' if entry.transaction_type == 'medical_aid' else 'DTH'}-{entry.record_id}",
                "type": aid_type,
                "payee": entry.member_name,
                "amount": float(entry.amount or 0),
                "releaseDate": entry.release_reference or "",
                "releasedBy": released_by,
                "reqId": f"{'MED' if entry.transaction_type == 'medical_aid' else 'DTH'}-{entry.record_id}",
            }
        )

    return JsonResponse({"ok": True, "releases": releases})


@require_POST
def treasurer_release_aid(request: HttpRequest):
    """Backend release endpoint for MedicalAid / DeathAid."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)

    target_id = (body.get("target_id") or "").strip()
    release_reference = (body.get("release_reference") or "").strip()
    received_by = (body.get("received_by") or "").strip()

    if not target_id:
        return JsonResponse(
            {"ok": False, "error": "target_id is required."}, status=400
        )
    if not release_reference:
        return JsonResponse(
            {"ok": False, "error": "release_reference is required."}, status=400
        )

    record = None
    table_name = None
    if target_id.startswith("MED-"):
        record_id = int(target_id.replace("MED-", ""))
        record = get_object_or_404(MedicalAid, medical_aid_id_PK=record_id)
        table_name = "medical_aid"
    elif target_id.startswith("DTH-"):
        record_id = int(target_id.replace("DTH-", ""))
        record = get_object_or_404(DeathAid, death_aid_id_PK=record_id)
        table_name = "death_aid"
    else:
        return JsonResponse(
            {"ok": False, "error": "Invalid target_id format."}, status=400
        )

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse(
            {"ok": False, "error": "Officer session missing."}, status=401
        )

    record.released_by_user_id_FK = officer
    record.release_reference = release_reference
    record.status = "Released"
    record.save(
        update_fields=[
            "released_by_user_id_FK",
            "release_reference",
            "status",
        ]
    )

    _record_audit_trail(
        table=table_name,
        record_id=record.pk,
        action="RELEASED",
        actor=officer,
        new={
            "status": "Released",
            "release_reference": release_reference,
            "received_by": received_by,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Aid released. Received by: {received_by}",
    )

    archive_transaction(
        table_name,
        record.pk,
        officer,
    )

    return JsonResponse(
        {"ok": True, "message": "Aid release recorded successfully."}
    )


@require_POST
def treasurer_medical_aid_add(request: HttpRequest):
    """Create a MedicalAid entry from the Treasurer medical aid form."""

    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard
    # Extract fields
    med_member = (request.POST.get("med_member") or "").strip()
    med_date = (request.POST.get("med_date") or "").strip()
    med_req_amount = (request.POST.get("med_req_amount") or "").strip()
    med_hospital = (request.POST.get("med_hospital") or "").strip()
    med_bill = (request.POST.get("med_bill") or "").strip()
    med_validation = (request.POST.get("med_validation") or "").strip()
    med_reason = (request.POST.get("med_reason") or "").strip()

    if not med_member:
        return JsonResponse({"ok": False, "error": "Beneficiary Member ID is required."}, status=400)
    if not med_date:
        return JsonResponse({"ok": False, "error": "Request Date is required."}, status=400)
    if not med_req_amount:
        med_req_amount = "0"

    # Resolve member
    member_obj, err = resolve_member_from_input(med_member)
    if err:
        return err

    # Once-per-year constraint per ARTICLE XI Section 1.b
    try:
        req_year = int(med_date[:4])
    except (ValueError, IndexError):
        req_year = timezone.now().year
    err_msg = check_medical_aid_once_per_year(member_obj, req_year)
    if err_msg:
        return JsonResponse({"ok": False, "error": err_msg}, status=400)

    from core_system.services.membership_fee_rules import (
        is_member_in_good_standing,
    )

    if not is_member_in_good_standing(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Member is not in good standing per ARTICLE XI Section 4."},
            status=400,
        )

    try:
        bill_value = float(med_bill) if med_bill else 0.0
    except ValueError:
        return JsonResponse(
            {"ok": False, "error": "Hospital bill must be a valid number."}, status=400
        )

    if bill_value <= get_accidental_sickness_aid_threshold():
        return JsonResponse(
            {
                "ok": False,
                "error": f"Hospital bill must exceed ₱{get_accidental_sickness_aid_threshold():,.2f} to qualify for accidental/sickness aid per By-Laws ARTICLE XI Section 1.b. Submitted: ₱{bill_value:,.2f}",
            },
            status=400,
        )

    # Optional file uploads (multi-file)
    recorded_by = resolve_officer_from_session(request)
    uploaded_files = request.FILES.getlist("med_photo_files")

    with transaction.atomic():
        aid = MedicalAid.objects.create(
            member_id_FK=member_obj,
            request_date=med_date,
            requested_amount=med_req_amount,
            hospital_name=med_hospital,
            hospital_bill_amount=med_bill,
            claim_year=timezone.now().year,
            document_status=med_reason or "Pending",
            policy_record_status="Pending",
            validated_aid_amount=0,
            status=med_validation or "Pending",
        )

        TransactionVerification.objects.create(
            table_name="medical_aid",
            record_id=aid.medical_aid_id_PK,
            verification_status="Pending",
        )

        for f in uploaded_files:
            if f and getattr(f, "size", 0) > 0:
                _link_proof_to_record(f, aid, recorded_by)

        _record_audit_trail(
            table="medical_aid",
            record_id=aid.medical_aid_id_PK,
            action="CREATED",
            actor=recorded_by,
            new={
                "member": member_obj,
                "request_date": med_date,
                "requested_amount": med_req_amount,
                "hospital_name": med_hospital,
                "hospital_bill_amount": med_bill,
                "status": med_validation or "Pending",
                "document_status": med_reason or "Pending",
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

    _broadcast_treasurer("aids")

    return JsonResponse({"ok": True, "aid_id": aid.medical_aid_id_PK})


@require_GET
def treasurer_medical_aid_list(request: HttpRequest):
    """Return MedicalAid records for the Treasurer dashboard."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    # MedicalAid model has no recorded_by_user_id_FK field.
    aids = (
        MedicalAid.objects.select_related("member_id_FK")
        .order_by("-medical_aid_id_PK")
    )

    rows = []
    for aid in aids:
        # UI expects the legacy key names used by AidsAndClaims.js:
        # - id (like MED-501)
        # - name, reason, hospital, bill, reqAmount, status, validation
        requested_amount = aid.requested_amount if aid.requested_amount is not None else aid.hospital_bill_amount

        rows.append(
            {
                # API keys used by static/js/Treasurer/AidsAndClaims.js
                "id": f"MED-{aid.medical_aid_id_PK}",
                "memberId": aid.member_id_FK.member_id_PK,
                "name": aid.member_id_FK.full_name,
                "date": aid.request_date.isoformat() if aid.request_date else "",
                # Your UI label uses `reason` for case description.
                "reason": aid.status or "Medical Aid Request",
                "reqAmount": float(requested_amount) if requested_amount is not None else 0,
                "hospital": aid.hospital_name or aid.member_id_FK.full_name,
                "bill": float(aid.hospital_bill_amount) if aid.hospital_bill_amount is not None else 0,
                "validation": aid.status or "Pending",
                "status": aid.status or "Pending",

                # Extra keys (kept for consistency with other callers/debugging)
                "aid_id": aid.medical_aid_id_PK,
                "member_id": aid.member_id_FK.member_id_PK,
                "member_name": aid.member_id_FK.full_name,
                "request_date": str(aid.request_date) if aid.request_date else "",
                "requested_amount": str(aid.requested_amount) if aid.requested_amount is not None else "",
                "hospital_bill_amount": str(aid.hospital_bill_amount)
                if getattr(aid, "hospital_bill_amount", None) is not None
                else "",
                "claim_year": aid.claim_year,
                "document_status": aid.document_status,
                "policy_record_status": aid.policy_record_status,
                "validated_aid_amount": str(aid.validated_aid_amount)
                if getattr(aid, "validated_aid_amount", None) is not None
                else "",
                "encoded_by": "",
            }
        )

    return JsonResponse({"ok": True, "medical_aids": rows})

# --- Death Aid (Claims) APIs (Treasurer) ---
@require_POST
def treasurer_death_aid_add(request: HttpRequest):
    """Create a DEATH_AID row from the Treasurer death aid claim form."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    death_member = (request.POST.get("death_member") or "").strip()
    death_deceased = (request.POST.get("death_deceased") or "").strip()
    death_rel = (request.POST.get("death_rel") or "").strip()
    death_type = (request.POST.get("death_type") or "").strip()
    death_claimant = (request.POST.get("death_claimant") or "").strip()
    death_contact = (request.POST.get("death_contact") or "").strip() or None
    death_bill = (request.POST.get("death_bill") or "").strip()
    death_date = (request.POST.get("death_date") or "").strip()
    death_funeral_location = (request.POST.get("death_funeral_location") or "").strip()
    death_interment_date = (request.POST.get("death_interment_date") or "").strip() or None

    if not death_member:
        return JsonResponse(
            {"ok": False, "error": "Associated Member ID is required."}, status=400
        )
    if not death_deceased:
        return JsonResponse(
            {"ok": False, "error": "Deceased person name is required."}, status=400
        )
    if not death_rel:
        return JsonResponse(
            {"ok": False, "error": "Relationship to member is required."}, status=400
        )
    death_rel_group = (request.POST.get("death_rel_group") or "").strip()
    if not death_rel_group:
        from core_system.constants.policy_constants import DEATH_AID_RELATIONSHIP_MAP
        death_rel_group = "immediate" if death_rel.lower() in [k.lower() for k in DEATH_AID_RELATIONSHIP_MAP] else "extended"
    if not death_claimant:
        return JsonResponse(
            {"ok": False, "error": "Claimant name is required."}, status=400
        )
    if not death_date:
        return JsonResponse(
            {"ok": False, "error": "Date of death is required."}, status=400
        )

    member_obj, err = resolve_member_from_input(death_member)
    if err:
        return err

    from core_system.services.membership_fee_rules import is_member_in_good_standing

    if is_exempt_from_dues_and_aid(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from death aid per ARTICLE XI Section 2."},
            status=400,
        )

    if not is_member_in_good_standing(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Member is not in good standing per ARTICLE XI Section 4."},
            status=400,
        )

    # Optional bill amount
    bill_value = None
    if death_bill:
        try:
            bill_value = float(death_bill)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Bill amount must be a valid number."}, status=400)

    from decimal import Decimal
    benefit_amount = Decimal(str(get_death_aid_amount(death_rel)))

    claimant_obj, _ = Claimant.objects.get_or_create(
        member_id_FK=member_obj,
        full_name=death_claimant,
        relationship_to_member=death_rel,
        defaults={
            "contact_number": death_contact,
            "authorization_status": "Pending Authorization",
            "relationship_group": death_rel_group,
        },
    )

    if death_contact is not None and not claimant_obj.contact_number:
        claimant_obj.contact_number = death_contact
        claimant_obj.save(update_fields=["contact_number"])

    treasurer_user = resolve_officer_from_session(request)

    uploaded_files = request.FILES.getlist("death_photo_files")

    with transaction.atomic():
        death_aid = DeathAid.objects.create(
            member_id_FK=member_obj,
            claimant_id_FK=claimant_obj,
            claim_date=death_date,
            claim_type=death_type or "Immediate Family",
            deceased_name=death_deceased,
            relationship_to_member=death_rel,
            relationship_group=death_rel_group,
            funeral_location=death_funeral_location,
            interment_date=death_interment_date,
            benefit_amount=benefit_amount,
            bill_amount=bill_value,
            document_status="Pending",
            status="Pending Verification",
            treasurer_validated_by_user_id_FK=treasurer_user,
            auditor_verified_by_user_id_FK=None,
            president_decided_by_user_id_FK=None,
            released_by_user_id_FK=None,
        )

        TransactionVerification.objects.create(
            table_name="death_aid",
            record_id=death_aid.death_aid_id_PK,
            verification_status="Pending",
        )

        for f in uploaded_files:
            if f and getattr(f, "size", 0) > 0:
                _link_proof_to_record(f, death_aid, treasurer_user)

        _record_audit_trail(
            table="death_aid",
            record_id=death_aid.death_aid_id_PK,
            action="CREATED",
            actor=treasurer_user,
            new={
                "member": member_obj,
                "claimant": claimant_obj,
                "claim_date": death_date,
                "claim_type": death_type or "Immediate Family",
                "deceased_name": death_deceased,
                "relationship_to_member": death_rel,
                "relationship_group": death_rel_group,
                "benefit_amount": str(benefit_amount),
                "status": "Pending Verification",
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

    _broadcast_treasurer("aids")

    return JsonResponse({"ok": True, "death_aid_id": death_aid.death_aid_id_PK})


@require_GET
def treasurer_death_aids_list(request: HttpRequest):
    """Return DeathAid rows for the Treasurer death aid table."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    aids = (
        DeathAid.objects.select_related("member_id_FK", "claimant_id_FK")
        .order_by("-death_aid_id_PK")
    )

    rows = []
    for a in aids:
        is_member = (
            a.deceased_name.strip().lower() == a.member_id_FK.full_name.strip().lower()
            or a.relationship_to_member.strip().lower() == "self"
        )
        rows.append(
            {
                "id": f"DTH-{a.death_aid_id_PK}",
                "memberId": a.member_id_FK.member_id_PK,
                "name": a.member_id_FK.full_name,
                "claimant": a.claimant_id_FK.full_name if a.claimant_id_FK else "",
                "deceased": a.deceased_name,
                "relationship": a.relationship_to_member,
                "relationshipGroup": a.relationship_group,
                "claimType": a.claim_type,
                "contact": a.claimant_id_FK.contact_number if a.claimant_id_FK else "",
                "date": a.claim_date.isoformat() if a.claim_date else "",
                "dateOfDeath": a.claim_date.isoformat() if a.claim_date else "",
                "bill_amount": float(a.bill_amount) if a.bill_amount is not None else 0,
                "benefit_amount": float(a.benefit_amount) if a.benefit_amount is not None else 0,
                "status": a.status or "Pending Verification",
                "document_status": a.document_status or "Pending",
                "is_member_deceased": is_member,
            }
        )

    return JsonResponse({"ok": True, "death_aids": rows})


@require_POST
@transaction.atomic
def treasurer_resubmit_entry(request: HttpRequest, table_name: str, record_id: int):

    """Flow B: Treasurer corrects and resubmits a rejected entry."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    if table_name not in MODEL_MAP:
        return JsonResponse({"ok": False, "error": "Invalid table."}, status=400)

    Model = MODEL_MAP[table_name]
    try:
        record = Model.objects.get(pk=int(record_id))
    except (ValueError, Model.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Record not found."}, status=404)

    old_snapshot = _serialize_for_audit({
        field.name: getattr(record, field.name)
        for field in record._meta.fields
    })

    officer = resolve_officer_from_session(request)

    # Explicitly bind Treasurer resubmission payload fields to model fields.
    # Bug A: the Treasurer frontend posts keys like fee_ref / fee_encoder / fee_month,
    # but membership_fee model fields are receipt_number / deposit_reference / month_covered, etc.
    if table_name == "membership_fee":
        payload_map = {
            "fee_ref": "receipt_number",
            "fee_encoder": "deposit_reference",
            "fee_method": "payment_method",
            "fee_date": "payment_date",
            "fee_month": "month_covered",
            "fee_status": "payment_status",
        }

        for payload_key, model_field in payload_map.items():
            if payload_key in request.POST:
                setattr(record, model_field, (request.POST.get(payload_key) or "").strip())

        # amount vs partial_amount
        if "fee_amount" in request.POST:
            setattr(record, "amount", (request.POST.get("fee_amount") or "").strip())
        if "fee_partial_amount" in request.POST:
            # Some UIs send both fee_amount + fee_partial_amount. We keep partial_amount consistent if present.
            if hasattr(record, "partial_amount"):
                setattr(record, "partial_amount", (request.POST.get("fee_partial_amount") or "").strip())
            # Keep amount in sync with partial amount for Partial resubmission.
            if (request.POST.get("fee_status") or "").strip() == "Partial":
                setattr(record, "amount", (request.POST.get("fee_partial_amount") or "").strip())

        # Persist with explicit update_fields to ensure DB columns are updated.
        update_fields = [
            "receipt_number",
            "deposit_reference",
            "payment_method",
            "payment_date",
            "month_covered",
            "payment_status",
            "amount",
        ]
        if hasattr(record, "partial_amount"):
            update_fields.append("partial_amount")
        record.save(update_fields=update_fields)
    else:
        # Default behavior for other tables that already use model-field key names.
        for field in UPDATABLE_FIELDS.get(table_name, []):
            if field in request.POST:
                setattr(record, field, request.POST[field])
        record.save()


    # Handle photo file upload for membership_fee resubmission
    if table_name == "membership_fee":
        uploaded = request.FILES.get("fee_photo_file")
        if uploaded and getattr(uploaded, "size", 0) > 0:
            _link_proof_to_record(uploaded, record, officer)

    # Reset verification state so the Auditor inbox re-loads this entry.
    # IMPORTANT: Auditor inbox only shows TransactionVerification rows with:
    # - verification_status == "Pending"
    current_tv = TransactionVerification.objects.filter(
        table_name=table_name,
        record_id=int(record_id),
    ).first()
    original_auditor_fk = current_tv.returned_by_auditor_id_FK_id if current_tv else None

    same_auditor = request.POST.get("same_auditor") == "true"
    updated_count = TransactionVerification.objects.filter(
        table_name=table_name,
        record_id=int(record_id),
    ).update(
        verification_status="Pending",
        auditor_id_FK_id=original_auditor_fk if (same_auditor and original_auditor_fk) else None,
        verified_at=None,
    )

    # Safety: ensure at least one row was updated; otherwise the resubmission
    # won't reappear in the Auditor Payments Audit inbox.
    if updated_count == 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "Resubmit failed: no TransactionVerification row matched.",
                "table_name": table_name,
                "record_id": record_id,
            },
            status=400,
        )

    new_snapshot = _serialize_for_audit({
        field.name: getattr(record, field.name)
        for field in record._meta.fields
    })

    _record_audit_trail(
        table=table_name,
        record_id=int(record_id),
        action="RESUBMITTED",
        actor=officer,
        old=old_snapshot,
        new=new_snapshot,
        ip=request.META.get("REMOTE_ADDR"),
        notes="Treasurer resubmitted entry after revision.",
    )

    _broadcast_treasurer("returned_entries")
    _broadcast_pending_counts()

    return JsonResponse({"ok": True})


# ==========================================================================
# TREASURER MEMBER LISTING & REVISION VIEWS (migrated from views_members_api)
# ==========================================================================

def _treasurer_payment_item_to_json(kind: str, obj) -> dict:
    member = getattr(obj, "member_id_FK", None)
    amount = getattr(obj, "amount", None)
    payment_date = getattr(obj, "payment_date", None)
    payment_method = getattr(obj, "payment_status", None) if kind == "membership_fee" else getattr(obj, "payment_method", None)
    month_covered = getattr(obj, "month_covered", None)

    return {
        "id": str(obj.fee_id_PK if kind == "membership_fee" else obj.dues_id_PK),
        "entity_id": int(obj.fee_id_PK if kind == "membership_fee" else obj.dues_id_PK),
        "type": "OTC Fee Payment" if kind == "membership_fee" else "Monthly Dues",
        "ref": getattr(obj, "receipt_number", None) or "",
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
        "month": month_covered or "N/A",
        "date": str(payment_date) if payment_date is not None else "",
        "method": str(payment_method) if payment_method is not None else "",
        "encoded_by": getattr(getattr(obj, "recorded_by_user_id_FK", None), "full_name", "") or "",
        "payment_status": getattr(obj, "payment_status", None) or "",
        "verification_status": "Pending",
    }


@require_GET
def treasurer_members_list(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    members = Member.objects.all().order_by("member_id_PK")
    return JsonResponse(
        {
            "ok": True,
            "members": [member_to_json(m) for m in members],
        }
    )


@require_GET
def treasurer_active_members_count(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    active_count = Member.objects.filter(membership_status="Active").count()

    return JsonResponse({"ok": True, "active_count": active_count})


@require_GET
def treasurer_records_requiring_revision(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    revision_verifications = TransactionVerification.objects.filter(
        verification_status="Returned for Revision"
    )

    items = []
    for tv in revision_verifications:
        table_name = str(tv.table_name).lower()
        if table_name not in MODEL_MAP:
            continue

        Model = MODEL_MAP[table_name]
        try:
            record = Model.objects.get(pk=tv.record_id)
        except Model.DoesNotExist:
            continue

        revision_log = GlobalAuditTrail.objects.filter(
            table_name=table_name,
            record_id=tv.record_id,
            action__in=["RETURNED", "CORRECTION_REQUIRED", "REJECTED"],
        ).order_by("-timestamp").first()

        if table_name in ("membership_fee", "monthly_dues"):
            item = _treasurer_payment_item_to_json(table_name.replace("_", ""), record)
            item["verificationStatus"] = tv.verification_status
            item["rejection_reason"] = revision_log.notes if revision_log else ""
            items.append(item)

    return JsonResponse({"ok": True, "records": items})


# ==========================================================================
# TREASURER MEMBER UPDATE/RETIRE VIEWS (migrated from member_api)
# ==========================================================================

@require_POST
def treasurer_member_update(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    payload_member_id = (request.POST.get("member_id") or "").strip()
    if not payload_member_id:
        return JsonResponse({"ok": False, "error": "member_id is required."}, status=400)

    member, err = resolve_member_from_input(payload_member_id)
    if err:
        return err

    fields = {}
    for field in [
        "full_name",
        "employee_id",
        "department",
        "position",
        "contact_number",
        "email",
        "employment_status",
        "membership_status",
        "member_type",
    ]:
        if field in request.POST:
            raw = (request.POST.get(field) or "").strip()
            fields[field] = raw if raw != "" else None

    if "employment_status" in fields and fields["employment_status"] is None:
        return JsonResponse({"ok": False, "error": "employment_status cannot be empty."}, status=400)
    if "membership_status" in fields and fields["membership_status"] is None:
        return JsonResponse({"ok": False, "error": "membership_status cannot be empty."}, status=400)

    for k, v in fields.items():
        setattr(member, k, v)

    if hasattr(member, "full_name") and not (member.full_name or "").strip():
        return JsonResponse({"ok": False, "error": "full_name is required."}, status=400)

    member.save()

    _broadcast_treasurer("members")

    return JsonResponse({"ok": True, "member": {"id": member.member_id_PK, "full_name": member.full_name}})


@require_POST
def treasurer_member_retire(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    payload_member_id = (request.POST.get("member_id") or "").strip()
    if not payload_member_id:
        return JsonResponse({"ok": False, "error": "member_id is required."}, status=400)

    member, err = resolve_member_from_input(payload_member_id)
    if err:
        return err

    member.membership_status = "retired"
    member.employment_status = "retired"
    member.save()

    _broadcast_treasurer("members")

    return JsonResponse({"ok": True, "member_id": member.member_id_PK})


# ============================================================================
# END TREASURER WORKSPACE VIEWS
# ==========================================================================

