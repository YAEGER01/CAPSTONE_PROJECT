import hashlib
import hmac
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
from core_system.api_utils import member_to_json
from core_system.guards import require_role
from core_system.logout_view import logout_view
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
    AuditorPaymentVerification,
    RevisionLog,
)
from core_system.constants.policy_constants import (
    get_accidental_sickness_aid_benefit,
    get_accidental_sickness_aid_threshold,
    get_death_aid_amount,
    get_expected_dues_amount,
    get_membership_fee_amount,
    get_monthly_dues_amount,
    is_exempt_from_dues_and_aid,
)
from django.core.files.storage import default_storage
from django.http import HttpRequest


MODEL_MAP = {
    "membership_fee": MembershipFee,
    "monthly_dues": MonthlyDues,
    "medical_aid": MedicalAid,
    "death_aid": DeathAid,
}

UPDATABLE_FIELDS = {
    "membership_fee": ["amount", "payment_method", "payment_status", "month_covered", "payment_date", "receipt_number", "deposit_reference"],
    "monthly_dues": ["month_covered", "amount", "payment_method", "payment_status", "receipt_number", "payment_date", "remittance_reference", "deduction_batch_reference"],
    "medical_aid": ["request_date", "requested_amount", "hospital_name", "hospital_bill_amount", "document_status", "status", "validated_aid_amount"],
    "death_aid": ["claim_date", "claim_type", "deceased_name", "relationship_to_member", "benefit_amount", "document_status", "status"],
}

MONTH_COVERED_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def normalize_month_covered(value: str) -> str:
    value = (value or "").strip()
    full_date_match = re.match(r"^(\d{4})-(0[1-9]|1[0-2])-(\d{2})$", value)
    if full_date_match:
        return f"{full_date_match.group(1)}-{full_date_match.group(2)}"

    return value


def get_request_month_covered(request: HttpRequest) -> str:
    for field_name in ("fee_month", "month_covered", "fee_month_covered", "covered_period"):
        value = request.POST.get(field_name)
        if value:
            return value.strip()

    return ""


def _sha256_of_uploaded_file(uploaded_file) -> str:
    """Stream-read an UploadedFile and return its hex SHA-256 digest."""
    sha = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        sha.update(chunk)
    return sha.hexdigest()


def _compute_row_signature(file_digest: str, object_id: int) -> str:
    """HMAC-SHA256 binding file hash + record PK + Django SECRET_KEY."""
    message = f"{file_digest}:{object_id}:{settings.SECRET_KEY}".encode()
    return hmac.new(
        settings.SECRET_KEY.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()


def _link_proof_to_record(uploaded_file, parent_instance, officer):
    """
    Shared helper: save file via FileField -> compute hashes -> create SupportingProof.
    Raises on failure so caller's transaction.atomic() rolls back.
    """
    file_digest = _sha256_of_uploaded_file(uploaded_file)
    content_type = ContentType.objects.get_for_model(parent_instance)

    proof = SupportingProof(
        content_type=content_type,
        object_id=parent_instance.pk,
        file=uploaded_file,
        file_name=uploaded_file.name,
        file_type=getattr(uploaded_file, "content_type", None) or "application/octet-stream",
        file_sha256=file_digest,
        uploaded_by=officer,
    )
    proof.row_signature = _compute_row_signature(file_digest, parent_instance.pk)
    proof.save()


PAYMENT_ENTITY_TYPE_LABELS = {
    "membership_fee": "MembershipFee",
    "monthly_dues": "MonthlyDues",
}


def _audit_evidence_filename(file_path):
    if not file_path:
        return ""
    return str(file_path).replace("\\", "/").split("/")[-1]


def _get_auditor_finding_evidence(table_name, record_id):
    archive = FinancialDocumentArchive.objects.filter(
        related_module=str(table_name).upper(),
        related_record_id=int(record_id),
        document_type="auditor_finding",
    ).order_by("-uploaded_at", "-document_id_PK").first()

    return _audit_evidence_filename(getattr(archive, "file_path", "")) if archive else ""


def _get_auditor_verification_remarks(table_name, record_id):
    # Legacy fallback (medical/death flows may still rely on AUDIT_FINDINGS_REPORT).
    entity_type = PAYMENT_ENTITY_TYPE_LABELS.get(str(table_name).lower(), str(table_name).title())
    report = AuditFindingsReport.objects.filter(
        report_title=f"Auditor findings: {entity_type} #{record_id}",
    ).order_by("-prepared_date", "-audit_report_id_PK").first()

    remarks = getattr(report, "findings_summary", "") or ""
    if remarks.strip():
        return remarks.strip()

    return "Auditor verified and forwarded to President for final executive sign-off."


def _get_auditor_payment_verification(table_name: str, record_id: int):
    return AuditorPaymentVerification.objects.filter(
        target_table=str(table_name).lower(),
        target_record_id=int(record_id),
    ).order_by("-verified_at").first()




# ==========================================================================
# TREASURER WORKSPACE VIEWS
# ==========================================================================
from core_system.constants.policy_constants import (
    get_death_aid_amount,
    get_expected_dues_amount,
    is_exempt_from_dues_and_aid,
)


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

    return render(request, "website/Treasurer/treasurer_dashboard.html", context)


# --- Member Enrollment / Listing APIs (Treasurer) ---
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.files.storage import default_storage
from django.http import HttpRequest
from core_system.models import Member

@require_POST
def treasurer_add_member(request: HttpRequest):
    """Enroll a new MEMBER row. Expects multipart/form-data from the frontend."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    prof_name = (request.POST.get("prof_name") or "").strip()
    prof_id = (request.POST.get("prof_id") or "").strip()
    prof_contact = (request.POST.get("prof_contact") or "").strip() or None
    prof_email = (request.POST.get("prof_email") or "").strip() or None
    prof_status = (request.POST.get("prof_status") or "Active").strip()
    prof_dept = (request.POST.get("prof_dept") or "").strip()
    prof_pos = (request.POST.get("prof_pos") or "").strip()

    if not prof_name:
        return JsonResponse(
            {"ok": False, "error": "Full Legal Name is required."}, status=400
        )
    if not prof_id:
        return JsonResponse(
            {"ok": False, "error": "Employee/Faculty ID is required."}, status=400
        )

    employee_id_max_length = Member._meta.get_field("employee_id").max_length
    if len(prof_id) > employee_id_max_length:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Employee/Faculty ID must be {employee_id_max_length} characters or fewer.",
            },
            status=400,
        )

    if not prof_status:
        return JsonResponse(
            {"ok": False, "error": "Membership Status is required."}, status=400
        )
    if prof_email and "@" not in prof_email:
        return JsonResponse(
            {"ok": False, "error": "Institutional Email looks invalid."}, status=400
        )
    employment_status = prof_status

    date_joined = timezone.now().date()
    uploaded = request.FILES.get("prof_photo_file")
    if uploaded and uploaded.size > 0:
        # keep under a deterministic folder
        default_storage.save(
            f"member_uploads/{timezone.now().strftime('%Y%m%d')}_{uploaded.name}",
            uploaded,
        )

    member = Member.objects.create(
        full_name=prof_name,
        employee_id=prof_id,
        department=prof_dept or None,
        position=prof_pos or None,
        contact_number=prof_contact,
        email=prof_email,
        employment_status=employment_status,
        membership_status=prof_status,
        member_type=prof_id,
        date_joined=date_joined,
    )

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
            },
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

    from core_system.models import RevisionLog
    from django.contrib.contenttypes.models import ContentType

    fee_ct = ContentType.objects.get_for_model(MembershipFee)
    returned_verifications = TransactionVerification.objects.filter(
        table_name="membership_fee",
        verification_status="Returned for Revision"
    ).select_related()

    rows = []
    for tv in returned_verifications:
        try:
            fee = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").get(
                fee_id_PK=tv.record_id
            )
        except MembershipFee.DoesNotExist:
            continue

        revision = RevisionLog.objects.filter(
            content_type=fee_ct,
            object_id=fee.fee_id_PK
        ).order_by("-created_at").first()

        rejection_reason = ""
        rejection_details = []
        if revision:
            rejection_reason = revision.rejection_reason or ""
        
        apv = AuditorPaymentVerification.objects.filter(
            target_table="membership_fee",
            target_record_id=fee.fee_id_PK
        ).first()
        if apv and apv.auditor_remarks:
            try:
                parsed = json.loads(apv.auditor_remarks)
                if isinstance(parsed, dict) and "rejection_details" in parsed:
                    rejection_details = parsed["rejection_details"]
            except (json.JSONDecodeError, TypeError):
                pass

        encoder_name = None
        if getattr(fee, "recorded_by_user_id_FK", None) is not None:
            encoder_name = getattr(fee.recorded_by_user_id_FK, "full_name", None)
            if not encoder_name:
                encoder_name = str(getattr(fee.recorded_by_user_id_FK, "user_id_PK", fee.recorded_by_user_id_FK_id))

        proof_url = None
        try:
            from core_system.models import SupportingProof
            proof = SupportingProof.objects.filter(
                content_type=fee_ct,
                object_id=fee.fee_id_PK
            ).order_by("-uploaded_at").first()
            if proof and getattr(proof, "file", None):
                proof_url = proof.file.url
        except Exception:
            proof_url = None

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

    from django.contrib.contenttypes.models import ContentType
    from core_system.models import RevisionLog

    dues_ct = ContentType.objects.get_for_model(MonthlyDues)
    returned_verifications = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status="Returned for Revision"
    ).select_related()

    rows = []
    for tv in returned_verifications:
        try:
            dues = MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK").get(
                dues_id_PK=tv.record_id
            )
        except MonthlyDues.DoesNotExist:
            continue

        revision = RevisionLog.objects.filter(
            content_type=dues_ct,
            object_id=dues.dues_id_PK
        ).order_by("-created_at").first()

        rejection_reason = ""
        rejection_details = []
        if revision:
            rejection_reason = revision.rejection_reason or ""

        apv = AuditorPaymentVerification.objects.filter(
            target_table="monthly_dues",
            target_record_id=dues.dues_id_PK
        ).first()
        if apv and apv.auditor_remarks:
            try:
                parsed = json.loads(apv.auditor_remarks)
                if isinstance(parsed, dict) and "rejection_details" in parsed:
                    rejection_details = parsed["rejection_details"]
            except (json.JSONDecodeError, TypeError):
                pass

        encoder_name = None
        if getattr(dues, "recorded_by_user_id_FK", None) is not None:
            encoder_name = getattr(dues.recorded_by_user_id_FK, "full_name", None)
            if not encoder_name:
                encoder_name = str(getattr(dues.recorded_by_user_id_FK, "user_id_PK", dues.recorded_by_user_id_FK_id))

        proof_url = None
        try:
            from core_system.models import SupportingProof
            proof = SupportingProof.objects.filter(
                content_type=dues_ct,
                object_id=dues.dues_id_PK
            ).order_by("-uploaded_at").first()
            if proof and getattr(proof, "file", None):
                proof_url = proof.file.url
        except Exception:
            proof_url = None

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
def treasurer_approved_transactions_total(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    total = 0

    approved_verifications = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Approved",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=False,
    ).select_related()

    for tv in approved_verifications:
        if tv.table_name.lower() == "membership_fee":
            fee = MembershipFee.objects.filter(fee_id_PK=tv.record_id).first()
            if fee:
                total += float(fee.amount)
        elif tv.table_name.lower() == "monthly_dues":
            dues = MonthlyDues.objects.filter(dues_id_PK=tv.record_id).first()
            if dues:
                total += float(dues.amount)

    return JsonResponse({"ok": True, "total": total})

#new_membership_add
@require_POST
def treasurer_membership_fee_add(request: HttpRequest):
    """Create a MEMBERSHIP_FEE row from the Treasurer membership fee form."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    from core_system.services.membership_fee_policy import (
        check_membership_fee_requirement,
    )
    from core_system.services.membership_fee_validation import (
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

    fee_member_clean = str(fee_member).strip()
    if fee_member_clean.upper().startswith("M-"):
        fee_member_clean = fee_member_clean[2:]

    try:
        member_pk = int(fee_member_clean)
    except ValueError:
        return JsonResponse({"ok": False, "error": "fee_member must be a numeric MEMBER PK (e.g., 1) or 'M-1'."}, status=400)

    try:
        member_obj = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    if is_exempt_from_dues_and_aid(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from monthly dues per ARTICLE XI Section 2."},
            status=400,
        )

    # Resolve officer session for potential exceptions and workflows
    stored_officer_id = request.session.get("officer_id")
    
    # Check policy requirement
    required_check = check_membership_fee_requirement(member_obj)
    if not required_check.required_to_pay:
        recorded_by = None
        if stored_officer_id is not None:
            try:
                recorded_by = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            except Exception:
                recorded_by = None

        if recorded_by is not None:
            from core_system.services.membership_fee_policy_exception_service import (
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
        from core_system.services.membership_fee_correction_service import (
            create_correction_artifacts_for_membership_fee,
        )
        from core_system.services.notifications_membership_fee import (
            notify_membership_fee_correction_required,
        )

        recorded_by = None
        if stored_officer_id is not None:
            try:
                recorded_by = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            except Exception:
                recorded_by = None

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

    recorded_by = None
    if stored_officer_id is not None:
        try:
            recorded_by = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            recorded_by = None

    if recorded_by is None:
        return JsonResponse({"ok": False, "error": "Unable to resolve officer session for encoding."}, status=401)

    from core_system.services.membership_fee_rules import (
        has_duplicate_membership_fee,
    )
    from core_system.services.notifications_membership_fee import (
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


def treasurer_monthly_dues_otc_add(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Invalid method."}, status=405)

    otc_member = (request.POST.get("otc_member") or "").strip()
    otc_month = (request.POST.get("otc_month") or "").strip()
    otc_amount = (request.POST.get("otc_amount") or "").strip()
    otc_date = (request.POST.get("otc_date") or "").strip()
    otc_method = (request.POST.get("otc_method") or "").strip() or "Unknown"
    otc_ref = (request.POST.get("otc_ref") or "").strip()

    if not otc_member:
        return JsonResponse(
            {"ok": False, "error": "Associated Member ID is required."}, status=400
        )
    if not otc_month:
        return JsonResponse(
            {"ok": False, "error": "Month Covered is required."}, status=400
        )
    if not otc_amount:
        return JsonResponse(
            {"ok": False, "error": "Amount Paid is required."}, status=400
        )
    if not otc_date:
        return JsonResponse(
            {"ok": False, "error": "Payment Date is required."}, status=400
        )
    if not otc_ref:
        return JsonResponse(
            {"ok": False, "error": "Receipt / Reference Number is required."},
            status=400,
        )

    otc_member_clean = str(otc_member).strip()
    if otc_member_clean.upper().startswith("M-"):
        otc_member_clean = otc_member_clean[2:]

    try:
        member_pk = int(otc_member_clean)
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "otc_member must be numeric MEMBER PK (e.g., 1) or 'M-1'.",
            },
            status=400,
        )

    try:
        member_obj = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    if is_exempt_from_dues_and_aid(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from monthly dues per ARTICLE XI Section 2."},
            status=400,
        )

    try:
        amount_value = float(otc_amount)
    except ValueError:
        return JsonResponse(
            {"ok": False, "error": "otc_amount must be a valid number."}, status=400
        )

    if abs(amount_value - get_monthly_dues_amount()) > 0.01:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Monthly dues amount must be exactly ₱{get_monthly_dues_amount():.2f} per ARTICLE XI Section 1.c.",
            },
            status=400,
        )

    recorded_by = None
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            recorded_by = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            recorded_by = None

    if recorded_by is None:
        return JsonResponse(
            {"ok": False, "error": "Unable to resolve officer session for encoding."},
            status=401,
        )

    uploaded = request.FILES.get("otc_photo_file")

    with transaction.atomic():
        dues = MonthlyDues.objects.create(
            member_id_FK=member_obj,
            month_covered=otc_month,
            amount=otc_amount,
            payment_method=otc_method,
            payment_status="Paid",
            payment_date=otc_date,
            receipt_number=otc_ref,
            recorded_by_user_id_FK=recorded_by,
        )

        TransactionVerification.objects.create(
            table_name="monthly_dues",
            record_id=dues.dues_id_PK,
            verification_status="Pending",
        )

        if uploaded and getattr(uploaded, "size", 0) > 0:
            _link_proof_to_record(uploaded, dues, recorded_by)

    return JsonResponse(
        {
            "ok": True,
            "dues": {
                "dues_id": dues.dues_id_PK,
                "ref": dues.receipt_number or "",
                "member_id": member_obj.member_id_PK,
                "member_name": member_obj.full_name,
                "month": dues.month_covered,
                "amount": str(dues.amount),
                "method": dues.payment_method,
                "date": str(dues.payment_date),
                "proof_attached": bool(uploaded and getattr(uploaded, "size", 0) > 0),
            },
        }
    )


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
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    sal_member = (request.POST.get("sal_member") or "").strip()
    sal_month = (request.POST.get("sal_month") or "").strip()
    sal_amount = (request.POST.get("sal_amount") or "").strip()
    sal_summary = (request.POST.get("sal_summary") or "").strip()
    sal_ref = (request.POST.get("sal_ref") or "").strip()

    if not sal_member:
        return JsonResponse(
            {"ok": False, "error": "Associated Member ID is required."}, status=400
        )
    if not sal_month:
        return JsonResponse(
            {"ok": False, "error": "Deduction Month is required."}, status=400
        )
    if not sal_amount:
        return JsonResponse(
            {"ok": False, "error": "Expected Dues Amount is required."}, status=400
        )
    if not sal_summary:
        return JsonResponse(
            {
                "ok": False,
                "error": "Accounting Deduction Summary Remarks are required.",
            },
            status=400,
        )
    if not sal_ref:
        return JsonResponse(
            {"ok": False, "error": "Remittance Reference Number is required."},
            status=400,
        )

    sal_member_clean = str(sal_member).strip()
    if sal_member_clean.upper().startswith("M-"):
        sal_member_clean = sal_member_clean[2:]

    try:
        member_pk = int(sal_member_clean)
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "sal_member must be a numeric MEMBER PK (e.g., 1) or 'M-1'.",
            },
            status=400,
        )

    try:
        member_obj = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    if is_exempt_from_dues_and_aid(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from monthly dues per ARTICLE XI Section 2."},
            status=400,
        )

    try:
        amount_value = float(sal_amount)
    except ValueError:
        return JsonResponse(
            {"ok": False, "error": "sal_amount must be a valid number."}, status=400
        )

    if abs(amount_value - get_monthly_dues_amount()) > 0.01:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Monthly dues amount must be exactly ₱{get_monthly_dues_amount():.2f} per ARTICLE XI Section 1.c.",
            },
            status=400,
        )

    recorded_by = None
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            recorded_by = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            recorded_by = None

    if recorded_by is None:
        return JsonResponse(
            {"ok": False, "error": "Unable to resolve officer session for encoding."},
            status=401,
        )

    # Optional backup document upload
    uploaded = request.FILES.get("sal_photo_file")
    if uploaded and getattr(uploaded, "size", 0) > 0:
        from django.core.files.storage import default_storage

        default_storage.save(
            f"salary_dues_uploads/{timezone.now().strftime('%Y%m%d')}_{uploaded.name}",
            uploaded,
        )

    try:
        payment_date = datetime.strptime(sal_month + "-01", "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse(
            {"ok": False, "error": "Invalid deduction month format."},
            status=400,
        )

    try:
        with transaction.atomic():
            dues = MonthlyDues.objects.create(
                member_id_FK=member_obj,
                month_covered=sal_month,
                amount=sal_amount,
                payment_method="Salary Deduction",
                payment_status="Paid",
                payment_date=payment_date,
                deduction_batch_reference=sal_summary,
                remittance_reference=sal_ref,
                recorded_by_user_id_FK=recorded_by,
            )

            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending",
            )
    except Exception as e:
        return JsonResponse(
            {"ok": False, "error": f"Failed to record salary deduction: {str(e)}"},
            status=500,
        )

    return JsonResponse(
        {
            "ok": True,
            "dues": {
                "dues_id": dues.dues_id_PK,
                "ref": dues.remittance_reference or "",
                "member_id": dues.member_id_FK.member_id_PK,
                "member_name": dues.member_id_FK.full_name,
                "month": dues.month_covered,
                "amount": str(dues.amount),
                "remarks": dues.deduction_batch_reference or "",
            },
        }
    )


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

    return JsonResponse({"ok": True, "salary_dues": rows})


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

    if not med_member:
        return JsonResponse({"ok": False, "error": "Beneficiary Member ID is required."}, status=400)
    if not med_date:
        return JsonResponse({"ok": False, "error": "Request Date is required."}, status=400)
    if not med_req_amount:
        return JsonResponse({"ok": False, "error": "Requested Amount is required."}, status=400)

    # Resolve member
    med_member_clean = med_member
    if med_member_clean.upper().startswith("M-"):
        med_member_clean = med_member_clean[2:]
    try:
        member_pk = int(med_member_clean)
    except ValueError:
        return JsonResponse({"ok": False, "error": "med_member must be numeric MEMBER PK or 'M-<id>'."}, status=400)
    try:
        member_obj = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    from core_system.services.membership_fee_policy import (
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

    # Optional file upload
    recorded_by = None
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            recorded_by = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            recorded_by = None

    uploaded = request.FILES.get("med_photo_file")

    with transaction.atomic():
        aid = MedicalAid.objects.create(
            member_id_FK=member_obj,
            request_date=med_date,
            requested_amount=med_req_amount,
            hospital_name=med_hospital,
            hospital_bill_amount=med_bill,
            claim_year=timezone.now().year,
            document_status="Pending",
            policy_record_status="Pending",
            validated_aid_amount=0,
            status=med_validation or "Pending",
        )

        TransactionVerification.objects.create(
            table_name="medical_aid",
            record_id=aid.medical_aid_id_PK,
            verification_status="Pending",
        )

        if uploaded and getattr(uploaded, "size", 0) > 0:
            _link_proof_to_record(uploaded, aid, recorded_by)

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
    death_benefit = (request.POST.get("death_benefit") or "").strip()
    death_date = (request.POST.get("death_date") or "").strip()

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
    if not death_claimant:
        return JsonResponse(
            {"ok": False, "error": "Claimant name is required."}, status=400
        )
    if not death_benefit:
        return JsonResponse(
            {"ok": False, "error": "Benefit amount is required."}, status=400
        )
    if not death_date:
        return JsonResponse(
            {"ok": False, "error": "Date of death is required."}, status=400
        )

    death_member_clean = str(death_member).strip()
    if death_member_clean.upper().startswith("M-"):
        death_member_clean = death_member_clean[2:]

    try:
        member_pk = int(death_member_clean)
    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "death_member must be a numeric MEMBER PK (e.g., 1) or 'M-1'.",
            },
            status=400,
        )

    try:
        member_obj = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    if is_exempt_from_dues_and_aid(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from death aid per ARTICLE XI Section 2."},
            status=400,
        )

    from core_system.services.membership_fee_policy import (
        is_member_in_good_standing,
    )

    if not is_member_in_good_standing(member_obj):
        return JsonResponse(
            {"ok": False, "error": "Member is not in good standing per ARTICLE XI Section 4."},
            status=400,
        )

    try:
        provided_benefit = float(death_benefit)
    except ValueError:
        return JsonResponse(
            {"ok": False, "error": "Benefit amount must be a number."}, status=400
        )

    claimant_obj, _ = Claimant.objects.get_or_create(
        member_id_FK=member_obj,
        full_name=death_claimant,
        relationship_to_member=death_rel,
        defaults={
            "contact_number": death_contact,
            "authorization_status": "Pending Authorization",
        },
    )

    if death_contact is not None and not claimant_obj.contact_number:
        claimant_obj.contact_number = death_contact
        claimant_obj.save(update_fields=["contact_number"])

    stored_officer_id = request.session.get("officer_id")
    treasurer_user = None
    if stored_officer_id is not None:
        try:
            treasurer_user = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            treasurer_user = None

    try:
        float(death_benefit)
    except ValueError:
        return JsonResponse({"ok": False, "error": "death_benefit must be a number."}, status=400)

    uploaded = request.FILES.get("death_photo_file")

    with transaction.atomic():
        death_aid = DeathAid.objects.create(
            member_id_FK=member_obj,
            claimant_id_FK=claimant_obj,
            claim_date=death_date,
            claim_type=death_type or "Immediate Family",
            deceased_name=death_deceased,
            relationship_to_member=death_rel,
            benefit_amount=death_benefit,
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

        if uploaded and getattr(uploaded, "size", 0) > 0:
            _link_proof_to_record(uploaded, death_aid, treasurer_user)

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
        rows.append(
            {
                "id": f"DTH-{a.death_aid_id_PK}",
                "memberId": a.member_id_FK.member_id_PK,
                "name": a.member_id_FK.full_name,
                "claimant": a.claimant_id_FK.full_name if a.claimant_id_FK else "",
                "deceased": a.deceased_name,
                "relationship": a.relationship_to_member,
                "claimType": a.claim_type,
                "contact": a.claimant_id_FK.contact_number if a.claimant_id_FK else "",
                "date": a.claim_date.isoformat() if a.claim_date else "",
                "dateOfDeath": a.claim_date.isoformat() if a.claim_date else "",
                "benefit_amount": float(a.benefit_amount) if a.benefit_amount is not None else 0,
                "status": a.status or "Pending Verification",
                "document_status": a.document_status or "Pending",
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
            stored_officer_id = request.session.get("officer_id")
            officer = None
            if stored_officer_id is not None:
                try:
                    officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
                except Exception:
                    officer = None
            _link_proof_to_record(uploaded, record, officer)

    # Reset verification state so the Auditor inbox re-loads this entry.
    # IMPORTANT: Auditor inbox only shows TransactionVerification rows with:
    # - verification_status == "Pending"
    # - auditor_id_FK is NULL
    updated_count = TransactionVerification.objects.filter(
        table_name=table_name,
        record_id=int(record_id),
    ).update(
        verification_status="Pending",
        auditor_id_FK_id=None,
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


    return JsonResponse({"ok": True})


# ============================================================================
# END TREASURER WORKSPACE VIEWS
# ==========================================================================

# ==========================================================================
# AUDITOR WORKSPACE VIEWS
# ==========================================================================
def auditor_dashboard(request):
    """Loads the main workspace shell frame for the Auditor role route context."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    officer_full_name = ""
    officer_role = "Auditor"

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
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    return render(request, "website/Auditor/auditor_dashboard.html", context)
# ==========================================================================
# END AUDITOR WORKSPACE VIEWS
# ==========================================================================

# ==========================================================================
# PRESIDENT WORKSPACE VIEWS
# ==========================================================================
def president_dashboard(request):
    """Loads the main workspace shell frame for the President role route context."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    return render(request, "website/President/president_dashboard.html")


@require_GET
def get_pending_presidential_payments(request):
    """
    Fetches all transactions awaiting Presidential verification from the transaction_verification table, 
    reconstructing member records and processing timelines.
    """
    from .models import RevisionLog

    verifications = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related('auditor_id_FK')
    
    data = []
    for v in verifications:
        # 1. Dynamically target the underlying payment row based on table_name string
        member_data = {}
        payment_details = {}
        approved_fields = {}
        
        if str(v.table_name).lower() == "monthly_dues":
            payment_record = MonthlyDues.objects.filter(dues_id_PK=v.record_id).select_related('member_id_FK', 'recorded_by_user_id_FK').first()
            if payment_record:
                p_member = payment_record.member_id_FK
                member_data = {
                    'member_name': p_member.full_name,
                    'employee_id': p_member.employee_id,
                    'department': p_member.department,
                    'membership_status': p_member.membership_status,
                    'contact_info': p_member.contact_number,
                }
                payment_details = {
                    'reference_code': payment_record.receipt_number or payment_record.deduction_batch_reference or "—",
                    'covered_period': payment_record.month_covered,
                    'amount_paid': float(payment_record.amount),
                    'expected': get_monthly_dues_amount() if str(v.table_name).lower() == "monthly_dues" else get_membership_fee_amount(),
                    'payment_method': payment_record.payment_method,
                    'encoder_name': payment_record.recorded_by_user_id_FK.full_name if payment_record.recorded_by_user_id_FK else "System"
                }
                method = (payment_record.payment_method or "").strip().lower()
                if method == "salary deduction":
                    approved_fields = {
                        'membership_type': "—",
                        'membership_ref': "—",
                        'membership_month': "—",
                        'membership_amount': 0,
                        'otc_month': "—",
                        'otc_amount': 0,
                        'otc_ref': "—",
                        'salary_month': payment_record.month_covered,
                        'salary_amount': float(payment_record.amount),
                        'salary_ref': payment_record.remittance_reference or payment_record.receipt_number or "",
                    }
                else:
                    approved_fields = {
                        'membership_type': "—",
                        'membership_ref': "—",
                        'membership_month': "—",
                        'membership_amount': 0,
                        'otc_month': payment_record.month_covered,
                        'otc_amount': float(payment_record.amount),
                        'otc_ref': payment_record.receipt_number or "",
                        'salary_month': "—",
                        'salary_amount': 0,
                        'salary_ref': "—",
                    }
                
        elif str(v.table_name).lower() == "membership_fee":
            payment_record = MembershipFee.objects.filter(fee_id_PK=v.record_id).select_related('member_id_FK', 'recorded_by_user_id_FK').first()
            if payment_record:
                p_member = payment_record.member_id_FK
                member_data = {
                    'member_name': p_member.full_name,
                    'employee_id': p_member.employee_id,
                    'department': p_member.department,
                    'membership_status': p_member.membership_status,
                    'contact_info': p_member.contact_number,
                }
                payment_details = {
                    'reference_code': payment_record.receipt_number or payment_record.deposit_reference or "—", 
                    'covered_period': payment_record.month_covered or "Initial Setup",
                    'amount_paid': float(payment_record.amount),
                    'expected': get_membership_fee_amount(),
                    'payment_method': payment_record.payment_method,
                    'encoder_name': payment_record.recorded_by_user_id_FK.full_name if payment_record.recorded_by_user_id_FK else "System"
                }
                approved_fields = {
                    'membership_type': "OTC Membership Fee",
                    'membership_ref': payment_record.receipt_number or payment_record.deposit_reference or "",
                    'membership_month': payment_record.month_covered or "",
                    'membership_amount': float(payment_record.amount),
                    'otc_month': "—",
                    'otc_amount': 0,
                    'otc_ref': "—",
                    'salary_month': "—",
                    'salary_amount': 0,
                    'salary_ref': "—",
                }
        
        # Skip this iteration if the underlying transaction record no longer exists
        if not member_data:
            continue

        # 2. Extract historic timeline details from RevisionLog using GenericForeignKey components
        # Map table_name to ContentType model name
        model_name_map = {
            "membership_fee": "membershipfee",
            "monthly_dues": "monthlydues",
        }
        ct_model = model_name_map.get(str(v.table_name).lower(), v.table_name.lower())
        try:
            content_type = ContentType.objects.get(model=ct_model)
            logs = RevisionLog.objects.filter(content_type=content_type, object_id=v.record_id).order_by('created_at')
        except ContentType.DoesNotExist:
            logs = []
        
        timeline_data = [{
            'timestamp': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'role': log.auditor_id_FK.role if log.auditor_id_FK else "Auditor",
            'user': log.auditor_id_FK.full_name if log.auditor_id_FK else "System Log",
            'action': "Auditor Flagged/Logged Entry",
            'notes': log.rejection_reason
        } for log in logs]

        # Combine payload matching your frontend dictionary keys
        apv = _get_auditor_payment_verification(str(v.table_name).lower(), v.record_id)

        # President “Auditor’s Verification Summary” fields (payments)
        # MUST come from AuditorPaymentVerification.
        auditor_full_name = "—"
        auditor_verified_date = "—"
        auditor_evidence = "—"
        auditor_remarks = "—"

        if apv:
            # Identity must come from OfficerUser via APV.auditor_id_FK
            auditor_full_name = (
                apv.auditor_id_FK.full_name if apv.auditor_id_FK_id else "—"
            )

            # Cross-check vs transaction_verification.verified_at via fallback
            auditor_verified_date = (
                apv.verified_at.strftime('%Y-%m-%d %H:%M:%S')
                if getattr(apv, "verified_at", None)
                else (v.verified_at.strftime('%Y-%m-%d %H:%M:%S') if v.verified_at else "—")
            )

            auditor_evidence = (
                _audit_evidence_filename(apv.evidence_file_path)
                if apv.evidence_file_path
                else "—"
            )

            auditor_remarks = (
                apv.auditor_remarks.strip()
                if apv.auditor_remarks and str(apv.auditor_remarks).strip()
                else "—"
            )
        else:
            # Fallback to transaction_verification if APV row missing
            auditor_full_name = v.auditor_id_FK.full_name if v.auditor_id_FK_id else "—"
            auditor_verified_date = (
                v.verified_at.strftime('%Y-%m-%d %H:%M:%S') if v.verified_at else "—"
            )
            auditor_evidence = "—"
            auditor_remarks = "—"

        # Match keys expected by static/js/President/payments_verification.js
        record_payload = {
            'id': v.verification_id,
            'auditorName': auditor_full_name,
            'auditorDate': auditor_verified_date,
            'auditorEvidence': auditor_evidence,
            'auditorRemarks': auditor_remarks,
            'timeline': timeline_data,
        }


        record_payload.update(member_data)
        record_payload.update(payment_details)
        record_payload.update(approved_fields)
        
        data.append(record_payload)
        
    return JsonResponse({'success': True, 'payments': data}, safe=False)


@require_http_methods(["POST"])
def submit_presidential_decision(request):
    """
    Commits final presidential approval decision or rejects it down using the real TransactionVerification table.
    """
    try:
        body = json.loads(request.body)
        target_id = body.get('target_id') # maps to verification_id
        decision = body.get('decision')   # 'Approved' or 'Rejected'
        remarks = body.get('remarks', '')
        
        # Grab the logged-in system operator from your Custom Officer User table
        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({'success': False, 'message': 'Officer session missing.'}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))
        verification = get_object_or_404(TransactionVerification, verification_id=target_id)
        
        if decision == 'Approved':
            verification.verification_status = 'Approved'
            verification.approved_at = timezone.now()
            action_str = 'Presidential Executive Approval Completed'
        elif decision == 'Rejected':
            verification.verification_status = 'Rejected'
            if not remarks:
                return JsonResponse({'success': False, 'message': 'Remarks are mandatory for rejections.'}, status=400)
            action_str = 'Flagged Deficient by Executive Order'
        else:
            return JsonResponse({'success': False, 'message': 'Invalid decision route.'}, status=400)
            
        verification.president_id_FK = officer
        verification.save()
        
        # Write history snapshot directly into your system's revision_log table
        target_content_type = ContentType.objects.get(model=verification.table_name.lower().replace("_", ""))
        RevisionLog.objects.create(
            content_type=target_content_type,
            object_id=verification.record_id,
            rejection_reason=remarks or "Executed standard presidential validation protocol.",
            snapshot_data={"action": action_str, "status": verification.verification_status},
            auditor_id_FK=officer
        )
        
        return JsonResponse({'success': True, 'message': f'Transaction status updated to {verification.verification_status}.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


        
# ==========================================================================
# END PRESIDENT WORKSPACE VIEWS
# ==========================================================================
def permission_denied_view(request, exception=None):
    """Renders the custom institutional 403 access alert page."""
    return render(request, "errors/403.html", status=403)

# --- Logout (custom officer session) ---
logout_view = logout_view
