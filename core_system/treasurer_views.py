import decimal
import hashlib
import json
import logging
import re
from datetime import datetime
from django.http import Http404, HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.db.models.functions import ExtractMonth
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core_system.api_utils import member_to_json

from core_system.guards import check_zero_trust, require_officer_session, require_role
from core_system.models import (
    AidTrackingPost,
    Contribution,
    FundTransaction,
    Member,
    MemberRegistrationRequest,
    MembershipFee,
    Notification,
    OfficerUser,
    MonthlyDues,
    PayrollBatch,
    PayrollDeduction,
    TransactionVerification,
    MedicalAid,
    DeathAid,
    Claimant,
    SupportingProof,
    FinancialDocumentArchive,
    AuditFindingsReport,
    TransactionArchive,
    GlobalAuditTrail,
    SensitiveReadLog,
    SystemSetting,
    MemberLedger,
    SalaryDeductionExemption,
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
from core_system.constants.status_constants import RegistrationStatus, Status
from core_system.services.email_service import (
    send_html_email,
    send_registration_status_update_email,
    send_registration_returned_email,
    send_registration_rejected_email,
    send_member_deduction_email,
)
from core_system.shared_view_utils import (
    MODEL_MAP,
    UPDATABLE_FIELDS,
    MONTH_COVERED_PATTERN,
    PAYMENT_ENTITY_TYPE_LABELS,
    normalize_month_covered,
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
    _officer_to_json,
    _record_audit_trail,
    _log_sensitive_read,
    _notify_release,
    set_treasurer_rejected,
    archive_transaction,
    _broadcast_pending_counts,
    _broadcast_to_group,
)
from django.core.files.storage import default_storage
from django.http import HttpRequest

logger = logging.getLogger(__name__)

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


@require_GET
def treasurer_officers_list(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    officers = OfficerUser.objects.select_related("department_id_FK").order_by("-created_at", "full_name")
    officers_json = [_officer_to_json(o) for o in officers]

    ip = request.META.get("REMOTE_ADDR")
    device_info = request.META.get("HTTP_USER_AGENT", "")
    actor_name = getattr(officer, "full_name", "") if officer else ""
    actor_role = getattr(officer, "role", "") if officer else ""

    _record_audit_trail(
        table="officer_user",
        record_id=0,
        action="READ",
        actor=officer,
        ip=ip,
        device_info=device_info,
        notes=f"Shared read by {actor_role} — officer dropdown loaded for member enrollment form on treasurer dashboard",
    )

    SensitiveReadLog.objects.bulk_create([
        SensitiveReadLog(
            table_name="officer_user",
            record_id=o["id"],
            reader_type=actor_role,
            reader_id=getattr(officer, "user_id_PK", None) if officer else None,
            device_info=device_info,
        )
        for o in officers_json
    ])

    return JsonResponse({"ok": True, "officers": officers_json})


@never_cache
def treasurer_dashboard(request):
    """Loads the unified Treasurer/Auditor executive workspace page."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
        "membership_fee_amount": get_membership_fee_amount(),
        "access_token": request.session.get("access_token", ""),
        "sickness_aid_threshold": get_accidental_sickness_aid_threshold(),
        "sickness_aid_benefit": get_accidental_sickness_aid_benefit(),
        "available_officers": list(
            OfficerUser.objects.filter(account_status__iexact="active", linked_member_profiles__isnull=True)
            .select_related("department_id_FK")
            .order_by("full_name")
            .distinct()
        ),
    }

    # If full_name missing/empty: use the fallback as required by the spec.
    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    context["returned_entries_count"] = TransactionVerification.objects.filter(
        table_name="membership_fee",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
    ).count()

    context["monthly_dues_returned_count"] = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
    ).count()

    context["medical_aid_returned_count"] = TransactionVerification.objects.filter(
        table_name="medical_aid",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
    ).count()

    context["death_aid_returned_count"] = TransactionVerification.objects.filter(
        table_name="death_aid",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
    ).count()

    context["active_aid_posts_count"] = AidTrackingPost.objects.filter(
        is_active=True,
    ).count()

    context["departments"] = list(
        Member.objects.filter(department__isnull=False)
        .values("department")
        .annotate(count=Count("member_id_PK"))
        .order_by("department")
    )
    context["departments_unassigned_count"] = Member.objects.filter(
        Q(department__isnull=True) | Q(department="")
    ).count()

    current_month = timezone.now().strftime("%Y-%m")
    dept_totals = dict(
        Member.objects.filter(department__isnull=False)
        .values("department")
        .annotate(total=Count("member_id_PK"))
        .values_list("department", "total")
    )
    dept_dues_paid = dict(
        MonthlyDues.objects.filter(month_covered=current_month)
        .values("member_id_FK__department")
        .annotate(dues_paid=Count("member_id_FK", distinct=True))
        .values_list("member_id_FK__department", "dues_paid")
    )
    dept_fees_paid = dict(
        MembershipFee.objects.filter(payment_status__in=["Full Payment", "Partial"])
        .values("member_id_FK__department")
        .annotate(fees_paid=Count("member_id_FK", distinct=True))
        .values_list("member_id_FK__department", "fees_paid")
    )

    context["department_payment_tracking"] = []
    for dept_name, total in sorted(dept_totals.items()):
        dues_paid = dept_dues_paid.get(dept_name, 0)
        fees_paid = dept_fees_paid.get(dept_name, 0)
        context["department_payment_tracking"].append({
            "department": dept_name,
            "total_members": total,
            "dues_paid_current_month": dues_paid,
            "dues_collection_rate": round((dues_paid / total * 100) if total > 0 else 0, 1),
            "membership_fee_paid": fees_paid,
            "fee_collection_rate": round((fees_paid / total * 100) if total > 0 else 0, 1),
        })

    return render(request, "website/Treasurer/treasurer_dashboard.html", context)


# --- Member Enrollment / Listing APIs (Treasurer) ---
@require_POST
def treasurer_add_member(request: HttpRequest):
    """
    Enroll a new MEMBER row and conditionally process an initial membership fee ledger
    record synchronously within a single atomic database context payload window.
    """
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    # Handle availability checks
    check_username = request.POST.get("check_username")
    check_email = request.POST.get("check_email")
    
    if check_username:
        if OfficerUser.objects.filter(username=check_username).exists():
            return JsonResponse({"ok": False, "error": f"Username '{check_username}' is already taken."}, status=409)
        if Member.objects.filter(employee_id=check_username).exists():
            return JsonResponse({"ok": False, "error": f"Employee ID '{check_username}' is already taken."}, status=409)
        return JsonResponse({"ok": True, "available": True})
    
    if check_email:
        if OfficerUser.objects.filter(email=check_email).exists():
            return JsonResponse({"ok": False, "error": f"Email '{check_email}' is already taken."}, status=409)
        if Member.objects.filter(email=check_email).exists():
            return JsonResponse({"ok": False, "error": f"Email '{check_email}' is already taken."}, status=409)
        return JsonResponse({"ok": True, "available": True})

    # Extract Core Member Variables
    first_name = (request.POST.get("first_name") or "").strip()
    middle_initial = (request.POST.get("middle_initial") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    username = (request.POST.get("username") or "").strip()
    prof_id = username  # Use username as employee_id
    prof_contact = (request.POST.get("prof_contact") or "").strip() or None
    prof_email = (request.POST.get("email") or "").strip() or None
    membership_category = (request.POST.get("membership_category") or "Permanent").strip()
    prof_dept = (request.POST.get("prof_dept") or "").strip()
    prof_pos = (request.POST.get("prof_pos") or "").strip()
    enrollment_amount = request.POST.get("enrollment_amount")
    payment_method = request.POST.get("payment_method")
    payment_date = request.POST.get("payment_date")
    notes = request.POST.get("notes", "").strip()

    # Combine name parts into full_name
    prof_name = f"{first_name} {middle_initial} {last_name}".strip() if middle_initial else f"{first_name} {last_name}".strip()

    # Validations: Member
    if not first_name or not last_name:
        return JsonResponse({"ok": False, "error": "First Name and Last Name are required."}, status=400)
    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not prof_email:
        return JsonResponse({"ok": False, "error": "Email is required for password delivery."}, status=400)

    if prof_email and "@" not in prof_email:
        return JsonResponse({"ok": False, "error": "Email looks invalid."}, status=400)

    if OfficerUser.objects.filter(username=username).exists():
        return JsonResponse(
            {"ok": False, "error": f"Username '{username}' is already taken."},
            status=409,
        )

    if Member.objects.filter(employee_id=username).exists():
        return JsonResponse(
            {"ok": False, "error": f"Employee ID '{username}' is already registered to another member."},
            status=409,
        )

    # Resolve Encoder User Identity context
    recorded_by = resolve_officer_from_session(request)
    
    # Auto-generate secure password before transaction
    from core_system.services.email_service import generate_secure_password
    generated_password = generate_secure_password()

    # Enforce transactional data integrity checks across models
    try:
        with transaction.atomic():
            # 1. Store Profile Attachments safely if provided
            prof_uploaded = request.FILES.get("prof_photo_file")
            if prof_uploaded and prof_uploaded.size > 0:
                import os
                safe_name = os.path.basename(prof_uploaded.name)
                if not safe_name:
                    safe_name = "upload"
                default_storage.save(
                    f"member_uploads/{timezone.now().strftime('%Y%m%d')}_{safe_name}",
                    prof_uploaded,
                )

            # 2. Create OfficerUser account for the member
            from core_system.auth_utils import hash_password
            
            officer_user = OfficerUser.objects.create(
                username=username,
                full_name=prof_name,
                password_hash=hash_password(generated_password),
                email=prof_email or "",
                role="Member",
                account_status="Active",
                must_change_password=True,
            )

            # 3. Provision Member Record Block
            member = Member.objects.create(
                full_name=prof_name,
                employee_id=prof_id,
                officer_user_id_FK=officer_user,
                department=prof_dept or None,
                position=prof_pos or None,
                contact_number=prof_contact,
                email=prof_email,
                employment_status="Active",
                membership_status=membership_category,
                member_type="Member",
                date_joined=timezone.now().date(),
            )

            # 4. Handle membership fee payment if amount and method provided
            if enrollment_amount and payment_method:
                from decimal import Decimal
                from datetime import datetime
                try:
                    amount = Decimal(enrollment_amount)
                    payment_dt = None
                    if payment_date:
                        payment_dt = datetime.strptime(payment_date, "%Y-%m-%d").date()
                    else:
                        payment_dt = timezone.now().date()
                    
                    # Handle proof file upload
                    proof_file = request.FILES.get("proof_file")
                    proof_path = None
                    if proof_file:
                        import os
                        safe_name = os.path.basename(proof_file.name)
                        if not safe_name:
                            safe_name = "proof"
                        proof_path = default_storage.save(
                            f"supporting_proofs/{timezone.now().strftime('%Y%m%d')}_{safe_name}",
                            proof_file
                        )
                    
                    fee = MembershipFee.objects.create(
                        member_id_FK=member,
                        receipt_number=f"SYS-TEMP-{int(timezone.now().timestamp())}",
                        amount=str(amount),
                        payment_date=payment_dt,
                        payment_method=payment_method,
                        payment_status="Pending",
                        supporting_proof=proof_path,
                        notes=notes,
                        recorded_by_user_id_FK=recorded_by,
                    )
                    TransactionVerification.objects.create(
                        table_name="membership_fee",
                        record_id=fee.fee_id_PK,
                        verification_status="Pending Treasurer Review",
                    )
                    _record_audit_trail(
                        table="membership_fee",
                        record_id=fee.fee_id_PK,
                        action="CREATED",
                        actor=recorded_by,
                        new={"member": member, "amount": str(fee.amount), "payment_date": str(fee.payment_date)},
                        ip=request.META.get("REMOTE_ADDR"),
                    )
                except Exception as e:
                    # If payment processing fails, still create the member but log the error
                    logger.exception("Failed to process membership fee payment for member %s", prof_name)
            else:
                # Auto-create pending membership fee if no payment provided
                fee = MembershipFee.objects.create(
                    member_id_FK=member,
                    receipt_number=f"SYS-TEMP-{int(timezone.now().timestamp())}",
                    amount=str(get_membership_fee_amount()),
                    payment_date=timezone.now().date(),
                    payment_method="Pending",
                    payment_status="Pending",
                    recorded_by_user_id_FK=recorded_by,
                )
                TransactionVerification.objects.create(
                    table_name="membership_fee",
                    record_id=fee.fee_id_PK,
                    verification_status="Pending",
                )
                _record_audit_trail(
                    table="membership_fee",
                    record_id=fee.fee_id_PK,
                    action="CREATED",
                    actor=recorded_by,
                    new={"member": member, "amount": str(fee.amount), "payment_date": str(fee.payment_date)},
                    ip=request.META.get("REMOTE_ADDR"),
                )

    except ValueError as val_err:
        return JsonResponse({"ok": False, "error": str(val_err)}, status=400)
    except Exception as ex:
        return JsonResponse({"ok": False, "error": f"Internal pipeline transactional exception: {str(ex)}"}, status=500)

    email_sent = True
    try:
        if member.email:
            email_sent = send_html_email(
                subject="Welcome to ISU CAUFA – Membership Registration Confirmed",
                recipient_list=[member.email],
                html_template="emails/member_added.html",
                context={
                    "full_name": member.full_name,
                    "employee_id": member.employee_id or "N/A",
                    "date_joined": member.date_joined.strftime("%B %d, %Y") if member.date_joined else str(timezone.now().date()),
                    "department": member.department or "",
                    "monthly_dues_amount": get_monthly_dues_amount(),
                    "membership_fee_amount": get_membership_fee_amount(),
                    "officer_contact": "",
                    "generated_password": generated_password,
                },
            )
    except Exception:
        pass

    try:
        Notification.objects.create(
            recipient_type="member",
            recipient_id=member.member_id_PK,
            recipient_name=member.full_name,
            recipient_contact=member.email or "",
            notification_type="membership_approved",
            message=f"Your ISU CAUFA membership has been registered. Welcome aboard, {member.full_name}!",
            category="general",
            delivery_status="sent",
        )
    except Exception:
        logger.exception("Failed to create welcome notification for member %s", member.full_name)

    _broadcast_treasurer("members")

    return JsonResponse(
        {
            "ok": True,
            "email_sent": email_sent,
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
                "officer_user_id": member.officer_user_id_FK_id,
                "date_joined": str(member.date_joined),
            },
            "message": "Member registered successfully. Password has been sent to the member's email address."
        }
    )


@require_POST
def treasurer_member_batch_add(request):
    """Accept multiple member entries in one JSON request and create them in a single transaction."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    try:
        body = json.loads(request.body)
        entries = body.get("entries", [])
    except (json.JSONDecodeError, TypeError, AttributeError):
        return JsonResponse({"ok": False, "error": "Invalid JSON payload."}, status=400)

    if not entries or not isinstance(entries, list):
        return JsonResponse({"ok": False, "error": "No entries provided."}, status=400)

    results = []
    recorded_by = resolve_officer_from_session(request)

    requested_usernames = [
        (e.get("username") or "").strip() for e in entries if e.get("username")
    ]
    requested_emails = [
        (e.get("email") or "").strip() for e in entries if e.get("email")
    ]

    existing_usernames = set(
        list(Member.objects.filter(employee_id__in=requested_usernames).values_list("employee_id", flat=True))
        + list(OfficerUser.objects.filter(username__in=requested_usernames).values_list("username", flat=True))
    )
    existing_emails = set(
        list(Member.objects.filter(email__in=requested_emails).values_list("email", flat=True))
        + list(OfficerUser.objects.filter(email__in=requested_emails).values_list("email", flat=True))
    )
    seen_usernames = set()
    seen_emails = set()

    with transaction.atomic():
        for entry in entries:
            first_name = (entry.get("first_name") or "").strip()
            middle_initial = (entry.get("middle_initial") or "").strip()
            last_name = (entry.get("last_name") or "").strip()
            username = (entry.get("username") or "").strip()
            email = (entry.get("email") or "").strip()
            status_val = (entry.get("membership_category") or "Permanent").strip() or "Permanent"
            prof_dept = (entry.get("prof_dept") or "").strip() or None
            prof_pos = (entry.get("prof_pos") or "").strip() or None
            prof_contact = (entry.get("prof_contact") or "").strip() or None
            enrollment_amount = (entry.get("enrollment_amount") or "").strip()
            payment_method = (entry.get("payment_method") or "").strip() or None
            payment_date = (entry.get("payment_date") or "").strip() or None
            notes = (entry.get("notes") or "").strip() or None
            full_name = (
                f"{first_name} {middle_initial} {last_name}".strip()
                if middle_initial
                else f"{first_name} {last_name}".strip()
            )

            if not first_name or not last_name:
                results.append({"ok": False, "name": full_name, "error": "First Name and Last Name are required."})
                continue
            if not username:
                results.append({"ok": False, "name": full_name, "error": "Username is required."})
                continue
            if not email or "@" not in email:
                results.append({"ok": False, "name": full_name, "error": "Valid email is required."})
                continue
            if username in existing_usernames or username in seen_usernames:
                results.append({"ok": False, "name": full_name, "error": f"Username '{username}' is already registered."})
                continue
            if email in existing_emails or email in seen_emails:
                results.append({"ok": False, "name": full_name, "error": f"Email '{email}' is already registered."})
                continue

            seen_usernames.add(username)
            seen_emails.add(email)

            try:
                from core_system.services.email_service import generate_secure_password
                generated_password = generate_secure_password()

                from core_system.auth_utils import hash_password
                officer_user = OfficerUser.objects.create(
                    username=username,
                    full_name=full_name,
                    password_hash=hash_password(generated_password),
                    email=email,
                    role="Member",
                    account_status="Active",
                    must_change_password=True,
                )

                member = Member.objects.create(
                    full_name=full_name,
                    employee_id=username,
                    officer_user_id_FK=officer_user,
                    department=prof_dept,
                    position=prof_pos,
                    contact_number=prof_contact,
                    email=email,
                    employment_status="Active",
                    membership_status=status_val,
                    member_type="Member",
                    date_joined=timezone.now().date(),
                )

                if member.membership_status in ("Permanent", "Temporary"):
                    from decimal import Decimal
                    from datetime import datetime

                    fee_amount = get_membership_fee_amount()
                    if enrollment_amount:
                        try:
                            fee_amount = Decimal(enrollment_amount)
                        except Exception:
                            pass

                    fee_date = timezone.now().date()
                    if payment_date:
                        try:
                            fee_date = datetime.strptime(payment_date, "%Y-%m-%d").date()
                        except Exception:
                            pass

                    MembershipFee.objects.create(
                        member_id_FK=member,
                        receipt_number=f"SYS-TEMP-{int(timezone.now().timestamp())}-{member.member_id_PK}",
                        amount=str(fee_amount),
                        payment_date=fee_date,
                        payment_method=payment_method or "Pending",
                        payment_status="Pending",
                        notes=notes,
                        recorded_by_user_id_FK=recorded_by,
                    )
                    TransactionVerification.objects.create(
                        table_name="membership_fee",
                        record_id=member.membershipfee_set.last().fee_id_PK,
                        verification_status="Pending",
                    )

                if email:
                    send_html_email(
                        subject="Welcome to ISU CAUFA – Membership Registration Confirmed",
                        recipient_list=[email],
                        html_template="emails/member_added.html",
                        context={
                            "full_name": full_name,
                            "employee_id": username or "N/A",
                            "date_joined": member.date_joined.strftime("%B %d, %Y") if member.date_joined else str(timezone.now().date()),
                            "department": prof_dept or "",
                            "monthly_dues_amount": get_monthly_dues_amount(),
                            "membership_fee_amount": get_membership_fee_amount(),
                            "officer_contact": "",
                            "generated_password": generated_password,
                        },
                    )
                results.append({"ok": True, "name": full_name, "id": member.member_id_PK})
            except Exception as ex:
                results.append({"ok": False, "name": full_name, "error": str(ex)})


    _broadcast_treasurer("members")
    return JsonResponse({"ok": True, "results": results})


@require_GET
def treasurer_membership_fee_list(request):
    """Return all membership fee ledger entries for the Treasurer dashboard."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
                "payment_date": str(f.payment_date),
                "payment_status": f.payment_status,
                "payment_method": f.payment_method,
                "deposit_reference": f.deposit_reference,
                "encoded_by": encoder_name or "",
            }
        )

    return JsonResponse({"ok": True, "fees": rows})


@require_GET
def treasurer_registration_requests_list(request):
    """Return public member registration requests for Treasurer review."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    # Only return pending and returned requests, not already-processed ones
    requests_qs = MemberRegistrationRequest.objects.filter(
        status__in=[
            RegistrationStatus.PENDING_TREASURER_REVIEW,
            RegistrationStatus.RETURNED_FOR_REVISION,
        ]
    ).select_related("processed_by_user_id_FK").order_by("-submitted_at")
    rows = []
    for req in requests_qs:
        rows.append({
            "request_id": req.request_id_PK,
            "full_name": req.full_name,
            "employee_id": req.employee_id,
            "email": req.email or "",
            "department": req.department or "",
            "position": req.position or "",
            "membership_category": req.membership_category,
            "payment_method": req.payment_method,
            "amount": str(req.amount),
            "receipt_number": req.receipt_number,
            "reference_number": req.reference_number or "",
            "payment_date": str(req.payment_date) if req.payment_date else "",
            "status": req.status,
            "returned_reason": req.returned_reason or "",
            "submitted_at": req.submitted_at.isoformat() if req.submitted_at else "",
            "processed_by": getattr(req.processed_by_user_id_FK, "full_name", "") if req.processed_by_user_id_FK else "",
            "proof_url": _get_proof_url(MemberRegistrationRequest, req.request_id_PK) or "",
        })

    return JsonResponse({"ok": True, "requests": rows})


@require_POST
def treasurer_registration_request_action(request: HttpRequest, request_id: int):
    """Accept or return a public registration request."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    request_row = get_object_or_404(MemberRegistrationRequest, request_id_PK=request_id)
    action = (request.POST.get("action") or "").strip().lower()
    reason = (request.POST.get("reason") or "").strip()

    if action not in {"approve", "return", "reject"}:
        return JsonResponse({"ok": False, "error": "Invalid action specified."}, status=400)

    if request_row.status not in {
        RegistrationStatus.PENDING_TREASURER_REVIEW,
        RegistrationStatus.RETURNED_FOR_REVISION,
    }:
        return JsonResponse(
            {"ok": False, "error": "This registration request has already been processed."},
            status=400,
        )

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Unable to resolve officer session."}, status=401)

    if action == "approve":
        with transaction.atomic():
            request_row.status = RegistrationStatus.TREASURER_VERIFIED
            request_row.processed_by_user_id_FK = officer
            request_row.treasurer_verified_by_user_id_FK = officer
            request_row.save()

        _record_audit_trail(
            table="member_registration_request",
            record_id=request_row.request_id_PK,
            action="TREASURER_VERIFIED",
            actor=officer,
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Treasurer verified registration request for {request_row.full_name}",
        )

        _broadcast_pending_counts()

        try:
            send_registration_status_update_email(
                request_row.email,
                request_row.full_name,
                new_status="Treasurer Verified",
                next_stage="Auditor Review",
            )
        except Exception:
            logger.exception("Failed to send status update email for %s", request_row.full_name)

        return JsonResponse({
            "ok": True,
            "status": request_row.status,
        })

    if action in {"return", "reject"}:
        if not reason:
            return JsonResponse({"ok": False, "error": "Reason is required for returning or rejecting a request."}, status=400)

        request_row.status = (
            RegistrationStatus.RETURNED_FOR_REVISION if action == "return" else RegistrationStatus.REJECTED
        )
        request_row.returned_reason = reason
        request_row.processed_by_user_id_FK = officer
        request_row.save()

        try:
            if action == "return":
                send_registration_returned_email(
                    request_row.email,
                    request_row.full_name,
                    reason=reason,
                )
            else:
                send_registration_rejected_email(
                    request_row.email,
                    request_row.full_name,
                    reason=reason,
                )
        except Exception:
            logger.exception("Failed to send %s email for %s", action, request_row.full_name)

        return JsonResponse({"ok": True, "status": request_row.status})


@require_GET
def treasurer_membership_fees_returned_list(request):
    """Return membership fee records that have been returned for revision."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="membership_fee",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED]
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="monthly_dues",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED]
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="medical_aid",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED]
    )

    rows = []
    record_ids = []
    for tv_rec in returned_verifications:
        try:
            aid = MedicalAid.objects.select_related("member_id_FK").get(
                medical_aid_id_PK=tv_rec.record_id
            )
        except MedicalAid.DoesNotExist:
            continue

        record_ids.append(aid.medical_aid_id_PK)

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
            "hospital_date": str(aid.hospital_date) if aid.hospital_date else "",
            "hospital_bill_amount": str(aid.hospital_bill_amount),
            "claim_year": str(aid.claim_year),
            "document_status": aid.document_status or "",
            "status": aid.status or "",
            "validated_aid_amount": str(aid.validated_aid_amount),
            "rejection_reason": rejection_reason,
            "rejection_details": rejection_details,
            "proof_url": proof_url or "",
        })

    _log_sensitive_read(request, "medical_aid", record_ids, "Treasurer viewed returned medical aid list")

    return JsonResponse({"ok": True, "records": rows})


@require_GET
def treasurer_death_aid_returned_list(request):
    """Return death aid records that have been returned for revision."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    returned_verifications = TransactionVerification.objects.filter(
        table_name="death_aid",
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED]
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    qs = TransactionArchive.objects.filter(
        status="Approved",
        transaction_type__in=["membership_fee", "monthly_dues"],
    ).select_related()

    total = sum(float(entry.amount or 0) for entry in qs)

    return JsonResponse({"ok": True, "total": total})


@require_GET
def cash_flow_summary(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    totals = FundTransaction.objects.aggregate(
        funds_in=Sum("amount", filter=Q(direction="inflow")),
        funds_out=Sum("amount", filter=Q(direction="outflow")),
    )
    funds_in = float(totals["funds_in"] or 0)
    funds_out = float(totals["funds_out"] or 0)

    return JsonResponse({
        "ok": True,
        "funds_in": funds_in,
        "funds_out": funds_out,
        "fund_balance": funds_in - funds_out,
    })


@require_GET
def treasurer_dashboard_inflow_outflow(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    total_in = float(totals["total_in"] or 0)
    total_out = float(totals["total_out"] or 0)
    fund_balance = total_in - total_out

    recent_inflows = FundTransaction.objects.filter(
        direction="inflow",
    ).order_by("-recorded_at")[:50]

    recent_outflows = FundTransaction.objects.filter(
        direction="outflow",
    ).order_by("-recorded_at")[:50]

    inflows = []
    for ft in recent_inflows:
        inflows.append({
            "description": ft.description,
            "source_type": ft.source_type,
            "amount": float(ft.amount),
            "recorded_at": str(ft.recorded_at.date()) if ft.recorded_at else "",
        })

    outflows = []
    for ft in recent_outflows:
        outflows.append({
            "description": ft.description,
            "source_type": ft.source_type,
            "amount": float(ft.amount),
            "recorded_at": str(ft.recorded_at.date()) if ft.recorded_at else "",
        })

    safety_threshold = float(SystemSetting.objects.get_or_create(
        setting_key="safety_threshold", defaults={"setting_value": "20000"}
    )[0].setting_value)

    return JsonResponse({
        "ok": True,
        "fund_balance": fund_balance,
        "money_in": total_in,
        "money_out": total_out,
        "inflows": inflows,
        "outflows": outflows,
        "safety_threshold": safety_threshold,
        "available": fund_balance - safety_threshold,
    })


@require_GET
def treasurer_monthly_flow(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    year = timezone.now().year

    membership_fee_map = {}
    monthly_dues_map = {}
    medical_aid_map = {}
    death_aid_map = {}
    fund_payment_map = {}
    contribution_map = {}

    for ft in FundTransaction.objects.filter(recorded_at__year=year).iterator():
        m = ft.recorded_at.month
        amount = float(ft.amount)

        if ft.direction == "inflow":
            if ft.source_type == "membership_fee":
                membership_fee_map[m] = membership_fee_map.get(m, 0) + amount
            elif ft.source_type == "monthly_dues":
                monthly_dues_map[m] = monthly_dues_map.get(m, 0) + amount
            elif ft.source_type == "contribution":
                contribution_map[m] = contribution_map.get(m, 0) + amount
        elif ft.direction == "outflow":
            if ft.source_type == "medical_aid":
                medical_aid_map[m] = medical_aid_map.get(m, 0) + amount
            elif ft.source_type == "death_aid":
                death_aid_map[m] = death_aid_map.get(m, 0) + amount
            elif ft.source_type == "aid_post_payment":
                fund_payment_map[m] = fund_payment_map.get(m, 0) + amount

    month_labels = []
    membership_fee_data = []
    monthly_dues_data = []
    medical_aid_data = []
    death_aid_data = []
    fund_payment_data = []
    contribution_data = []

    for m in range(1, 13):
        month_labels.append(f"{year}-{m:02d}")
        membership_fee_data.append(membership_fee_map.get(m, 0))
        monthly_dues_data.append(monthly_dues_map.get(m, 0))
        medical_aid_data.append(medical_aid_map.get(m, 0))
        death_aid_data.append(death_aid_map.get(m, 0))
        fund_payment_data.append(fund_payment_map.get(m, 0))
        contribution_data.append(contribution_map.get(m, 0))

    return JsonResponse({
        "ok": True,
        "months": month_labels,
        "membership_fee": membership_fee_data,
        "monthly_dues": monthly_dues_data,
        "medical_aid": medical_aid_data,
        "death_aid": death_aid_data,
        "fund_payment": fund_payment_data,
        "contribution": contribution_data,
    })


    
#new_membership_add
@require_POST
def treasurer_membership_fee_add(request: HttpRequest):
    """Create a MEMBERSHIP_FEE row from the Treasurer membership fee form."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
            payment_date=fee_date,
            payment_method=fee_method,
            payment_status=fee_status,
            deposit_reference=fee_encoder or None,
            recorded_by_user_id_FK=recorded_by,
        )

        TransactionVerification.objects.create(
            table_name="membership_fee",
            record_id=fee.fee_id_PK,
            verification_status="Pending Auditor Review",
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
            if MonthlyDues.objects.filter(member_id_FK=member, month_covered=month).exists():
                return JsonResponse(
                    {"ok": False, "error": "Monthly dues already recorded for this member and month."},
                    status=409,
                )
            is_advance = month > timezone.now().strftime("%Y-%m")
            dues = MonthlyDues.objects.create(
                member_id_FK=member,
                month_covered=month,
                amount=str(amount_decimal),
                payment_method=method,
                payment_status="Pending",
                payment_date=date_raw,
                receipt_number=ref,
                recorded_by_user_id_FK=officer,
                is_advance=is_advance,
                treasurer_status="Treasurer Approved",
                treasurer_id_FK=officer,
                treasurer_approved_at=timezone.now(),
                auditor_status="Pending Auditor Review",
            )
            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending Auditor Review",
            )
            if uploaded and getattr(uploaded, "size", 0) > 0:
                _link_proof_to_record(uploaded, dues, officer)
            _record_audit_trail(
                table="monthly_dues",
                record_id=dues.dues_id_PK,
                action="CREATED",
                actor=officer,
                new={"member": member, "month_covered": month, "amount": str(amount_decimal),
                     "payment_method": method, "payment_date": date_raw, "receipt_number": ref,
                     "is_advance": is_advance},
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
            if MonthlyDues.objects.filter(member_id_FK=member, month_covered=month).exists():
                return JsonResponse(
                    {"ok": False, "error": "Monthly dues already recorded for this member and month."},
                    status=409,
                )
            is_advance = month > timezone.now().strftime("%Y-%m")
            dues = MonthlyDues.objects.create(
                member_id_FK=member,
                month_covered=month,
                amount=str(amount_decimal),
                payment_method="Salary Deduction",
                payment_status="Pending",
                payment_date=payment_date,
                deduction_batch_reference=summary,
                remittance_reference=sal_ref,
                recorded_by_user_id_FK=officer,
                is_advance=is_advance,
                treasurer_status="Treasurer Approved",
                treasurer_id_FK=officer,
                treasurer_approved_at=timezone.now(),
                auditor_status="Pending Auditor Review",
            )
            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending Auditor Review",
            )
            if uploaded and getattr(uploaded, "size", 0) > 0:
                _link_proof_to_record(uploaded, dues, officer)

            # NOTE: MemberLedger is intentionally NOT written here. Monthly dues
            # reach the ledger once — at President approval — so MemberLedger and
            # FundTransaction always describe the same approved financial event.

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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    dues = (
        MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
        .filter(treasurer_status="Pending Treasurer Review")
        .order_by("-dues_id_PK")
    )

    rows = []
    for d in dues:
        rows.append(
            {
                "dues_id": d.dues_id_PK,
                "dues_id_PK": d.dues_id_PK,
                "ref": d.receipt_number or "",
                "member_id": d.member_id_FK.member_id_PK,
                "member_name": d.member_id_FK.full_name,
                "member_employee_id": d.member_id_FK.employee_id,
                "month": d.month_covered,
                "month_covered": d.month_covered,
                "amount": str(d.amount),
                "method": d.payment_method,
                "payment_method": d.payment_method,
                "date": str(d.payment_date) if d.payment_date else "",
                "payment_status": d.payment_status,
                "treasurer_status": d.treasurer_status,
                "auditor_status": d.auditor_status,
                "president_status": d.president_status,
            }
        )

    return JsonResponse({"ok": True, "otc_dues": rows, "dues": rows})


@require_GET
def treasurer_monthly_dues_detail(request: HttpRequest, dues_id: int):
    """Get full details of a monthly dues submission for review."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    dues = get_object_or_404(
        MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK"),
        dues_id_PK=dues_id
    )

    # Get supporting proofs
    ct = ContentType.objects.get_for_model(MonthlyDues)
    proofs = SupportingProof.objects.filter(
        content_type=ct,
        object_id=dues.dues_id_PK
    ).order_by("-uploaded_at")

    supporting_proofs = []
    for p in proofs:
        supporting_proofs.append({
            "proof_id": p.proof_id_PK,
            "file_name": p.file_name,
            "file_type": p.file_type,
            "file_url": p.file.url if p.file else "",
            "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else "",
        })

    return JsonResponse({
        "ok": True,
        "dues": {
            "dues_id_PK": dues.dues_id_PK,
            "member_id_PK": dues.member_id_FK.member_id_PK,
            "member_name": dues.member_id_FK.full_name,
            "member_employee_id": dues.member_id_FK.employee_id,
            "member_department": dues.member_id_FK.department or "",
            "member_position": dues.member_id_FK.position or "",
            "member_contact": dues.member_id_FK.contact_number or "",
            "month_covered": dues.month_covered,
            "amount": str(dues.amount),
            "payment_method": dues.payment_method,
            "payment_status": dues.payment_status,
            "payment_date": dues.payment_date.isoformat() if dues.payment_date else "",
            "receipt_number": dues.receipt_number or "",
            "treasurer_status": dues.treasurer_status,
            "auditor_status": dues.auditor_status,
            "president_status": dues.president_status,
            "treasurer_remarks": dues.treasurer_remarks or "",
            "auditor_remarks": dues.auditor_remarks or "",
            "president_remarks": dues.president_remarks or "",
            "recorded_by": dues.recorded_by_user_id_FK.full_name if dues.recorded_by_user_id_FK else "",
            "recorded_at": dues.payment_date.isoformat() if dues.payment_date else "",
            "supporting_proofs": supporting_proofs,
        }
    })


@require_POST
def treasurer_monthly_dues_salary_add(request: HttpRequest):
    """Legacy Salary Deduction add wrapper — delegates to unified view."""
    return treasurer_monthly_dues_add(request)


@require_GET
def treasurer_monthly_dues_salary_list(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
                "recorded_by": d.recorded_by_user_id_FK.full_name if d.recorded_by_user_id_FK else "Unknown",
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
                "recorded_by": d.recorded_by_user_id_FK.full_name if d.recorded_by_user_id_FK else "Unknown",
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


@require_GET
def treasurer_monthly_dues_tracking(request):
    """Returns per-member per-month dues status for a given year."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    year = request.GET.get("year", "")
    if not year or not year.isdigit():
        return JsonResponse({"ok": False, "error": "year query parameter required."}, status=400)

    prefix = year + "-"
    dues = MonthlyDues.objects.filter(
        month_covered__startswith=prefix
    ).select_related("member_id_FK")

    tracking = {}
    for d in dues:
        mid = d.member_id_FK.member_id_PK
        if mid not in tracking:
            tracking[mid] = {}
        month_key = d.month_covered
        if d.payment_method == "Salary Deduction":
            status = "paid"
        elif d.payment_status == "Full Payment":
            status = "paid"
        elif d.payment_status == "Paid":
            status = "paid"
        else:
            status = "partial"
        tracking[mid][month_key] = status

    return JsonResponse({"ok": True, "year": int(year), "tracking": tracking})


@require_POST
def treasurer_approve_monthly_dues(request: HttpRequest):
    """Treasurer approves or rejects monthly dues payments, supporting single or batch approvals."""
    guard = require_role(request, role=["Treasurer"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    action = data.get("action")
    remarks = data.get("remarks", "")

    if action not in ["approve", "reject"]:
        return JsonResponse({"ok": False, "error": "Missing required fields: action"}, status=400)

    raw_dues_ids = data.get("dues_ids") or data.get("dues_id")
    if isinstance(raw_dues_ids, list):
        dues_ids = [int(item) for item in raw_dues_ids if str(item).strip()]
    elif raw_dues_ids is not None:
        dues_ids = [int(raw_dues_ids)]
    else:
        dues_ids = []

    if not dues_ids:
        return JsonResponse({"ok": False, "error": "Missing required fields: dues_id or dues_ids"}, status=400)

    with transaction.atomic():
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
        processed = 0
        skipped = 0

        for dues_id in dues_ids:
            dues = MonthlyDues.objects.select_for_update().filter(dues_id_PK=dues_id).first()
            if dues is None:
                skipped += 1
                continue

            if action == "approve" and dues.treasurer_status not in ("Pending Treasurer Review", "Pending"):
                skipped += 1
                continue

            if action == "approve":
                dues.treasurer_status = "Treasurer Verified"
                dues.treasurer_id_FK = officer
                dues.treasurer_remarks = remarks
                dues.treasurer_approved_at = timezone.now()
                dues.auditor_status = "Pending Auditor Review"
                dues.save()

                tv = TransactionVerification.objects.filter(
                    table_name="monthly_dues",
                    record_id=dues_id,
                ).order_by("-verification_id").first()
                if tv:
                    tv.verification_status = "Pending Auditor Review"
                    tv.auditor_id_FK = None
                    tv.save()
                else:
                    TransactionVerification.objects.create(
                        table_name="monthly_dues",
                        record_id=dues_id,
                        target_category="payment",
                        verification_status="Pending Auditor Review",
                    )

                _record_audit_trail(
                    table="monthly_dues",
                    record_id=dues_id,
                    action="Treasurer Approved",
                    actor=officer,
                    new={"member": dues.member_id_FK, "month_covered": str(dues.month_covered), "amount": str(dues.amount)},
                    ip=request.META.get("REMOTE_ADDR"),
                    notes=remarks,
                )
            else:
                set_treasurer_rejected(
                    "monthly_dues",
                    dues_id,
                    officer,
                    remarks,
                    request,
                    member=dues.member_id_FK,
                    is_rejected=False,
                    extra_updates={
                        "treasurer_id_FK": officer,
                        "treasurer_remarks": remarks,
                        "treasurer_approved_at": timezone.now(),
                    },
                    details=f"Your monthly dues payment for {dues.month_covered} was returned for revision.",
                )

            processed += 1

        return JsonResponse({
            "ok": True,
            "message": f"Monthly dues payments {'approved' if action == 'approve' else 'returned'} successfully.",
            "processed": processed,
            "skipped": skipped,
        })


@require_POST
def treasurer_salary_bulk_preview(request: HttpRequest):
    """Preview active members for bulk salary deduction processing."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
        "next_batch_ref": _next_batch_ref(sal_month),
    })


def _next_batch_ref(month_str):
    """Generate the next batch reference: ISU-CAUFA-{YY}-{N}."""
    yy = month_str.split("-")[0][-2:]
    prefix = f"ISU-CAUFA-{yy}-"
    existing = MonthlyDues.objects.filter(
        remittance_reference__startswith=prefix,
    ).values_list("remittance_reference", flat=True)
    max_n = 0
    for ref in existing:
        try:
            n = int(ref[len(prefix):])
            if n > max_n:
                max_n = n
        except (ValueError, IndexError):
            continue
    return f"{prefix}{max_n + 1}"


@require_GET
def treasurer_next_batch_ref(request: HttpRequest):
    """Return the next auto-generated batch ref for a given month."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    month = (request.GET.get("month") or "").strip()
    if not month:
        return JsonResponse({"ok": False, "error": "month is required."}, status=400)

    return JsonResponse({
        "ok": True,
        "next_batch_ref": _next_batch_ref(month),
    })


@require_POST
def treasurer_salary_bulk_process(request: HttpRequest):
    """Create salary deduction records for multiple members in one batch."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    sal_month = (request.POST.get("sal_month") or "").strip()
    summary = (request.POST.get("summary") or "").strip()
    member_ids_raw = (request.POST.get("member_ids") or "").strip()
    uploaded = request.FILES.get("sal_photo_file")

    if not sal_month:
        return JsonResponse({"ok": False, "error": "sal_month is required."}, status=400)
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

    # Auto-generate batch reference
    batch_ref = _next_batch_ref(sal_month)

    # Deduplicate member_ids
    unique_ids = list(set(member_ids))

    # Fetch members in bulk
    members_map = {
        m.member_id_PK: m
        for m in Member.objects.filter(member_id_PK__in=unique_ids)
    }

    processed = 0
    skipped = 0
    created_dues = []

    with transaction.atomic():
        # Use select_for_update to prevent race conditions
        if MonthlyDues.objects.select_for_update().filter(
            payment_method="Salary Deduction",
            month_covered=sal_month,
        ).exists():
            return JsonResponse({
                "ok": False,
                "error": f"Salary deductions for {sal_month} have already been processed. Duplicate month not allowed.",
            }, status=409)

        for mid in unique_ids:
            member = members_map.get(mid)
            if not member:
                skipped += 1
                continue
            if str(member.membership_status) == "retired":
                skipped += 1
                continue

            dues = MonthlyDues.objects.create(
                member_id_FK=member,
                month_covered=sal_month,
                amount=str(expected_amount),
                payment_method="Salary Deduction",
                payment_status="Pending",
                payment_date=payment_date,
                deduction_batch_reference=summary,
                remittance_reference=batch_ref,
                recorded_by_user_id_FK=officer,
            )
            TransactionVerification.objects.create(
                table_name="monthly_dues",
                record_id=dues.dues_id_PK,
                verification_status="Pending Auditor Review",
            )
            if uploaded and getattr(uploaded, "size", 0) > 0:
                _link_proof_to_record(uploaded, dues, officer)

            # NOTE: MemberLedger is intentionally NOT written here. Monthly dues
            # reach the ledger once — at President approval — so MemberLedger and
            # FundTransaction always describe the same approved financial event.

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
def treasurer_releases_list(request: HttpRequest):
    """Return released transactions from the archive."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

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

    if record.status not in ("Approved", "President Approved"):
        return JsonResponse(
            {"ok": False, "error": "Aid has not been approved by the President yet. Only approved aids can be released."},
            status=400,
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

    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # Extract fields
    med_member = (request.POST.get("med_member") or "").strip()
    med_date = (request.POST.get("med_date") or "").strip()
    med_req_amount = (request.POST.get("med_req_amount") or "").strip()
    med_hospital = (request.POST.get("med_hospital") or "").strip()
    med_hospital_date = (request.POST.get("med_hospital_date") or "").strip()
    med_bill = (request.POST.get("med_bill") or "").strip()
    med_validation = (request.POST.get("med_validation") or "").strip()
    med_reason = (request.POST.get("med_reason") or "").strip()
    med_source = (request.POST.get("med_source") or "").strip()

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
            hospital_date=med_hospital_date or None,
            hospital_bill_amount=med_bill,
            claim_year=req_year,
            document_status=med_reason or "Pending",
            policy_record_status="Pending",
            validated_aid_amount=get_accidental_sickness_aid_benefit(),
            status=med_validation or "Pending",
            disbursement_source=med_source if med_source in ("fund", "direct") else None,
            treasurer_validated_by_user_id_FK=recorded_by,
        )

        TransactionVerification.objects.create(
            table_name="medical_aid",
            record_id=aid.medical_aid_id_PK,
            verification_status="Pending Auditor Review",
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
                "hospital_date": med_hospital_date,
                "hospital_bill_amount": med_bill,
                "status": med_validation or "Pending",
                "document_status": med_reason or "Pending",
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

    _broadcast_treasurer("aids")

    return JsonResponse({"ok": True, "aid_id": aid.medical_aid_id_PK})


@require_POST
@transaction.atomic
def treasurer_medical_aid_batch_add(request: HttpRequest):
    """Create MedicalAid entries for multiple members in one transaction."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    from core_system.services.membership_fee_rules import is_member_in_good_standing

    try:
        batch_data = json.loads(request.POST.get("med_batch_data", "[]"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid batch data."}, status=400)

    if not isinstance(batch_data, list) or len(batch_data) == 0:
        return JsonResponse({"ok": False, "error": "No members in batch."}, status=400)

    if len(batch_data) > 5:
        return JsonResponse({"ok": False, "error": "Maximum 5 members per batch."}, status=400)

    recorded_by = resolve_officer_from_session(request)
    created_ids = []

    for idx, entry in enumerate(batch_data):
        member_id = (entry.get("member_id") or "").strip()
        request_date = (entry.get("request_date") or "").strip()
        reason = (entry.get("reason") or "").strip()
        hospital = (entry.get("hospital") or "").strip()
        hospital_date = (entry.get("hospital_date") or "").strip()
        bill_str = (entry.get("bill") or "").strip()

        if not member_id or not request_date or not reason or not bill_str:
            return JsonResponse({
                "ok": False,
                "error": f"Card {idx + 1}: Member, Date, Reason, and Bill are required."
            }, status=400)

        # Resolve member
        member_obj, err = resolve_member_from_input(member_id)
        if err:
            return JsonResponse({
                "ok": False,
                "error": f"Card {idx + 1} ({member_id}): Could not resolve member."
            }, status=400)

        # Once-per-year constraint
        try:
            req_year = int(request_date[:4])
        except (ValueError, IndexError):
            req_year = timezone.now().year
        err_msg = check_medical_aid_once_per_year(member_obj, req_year)
        if err_msg:
            return JsonResponse({
                "ok": False,
                "error": f"Card {idx + 1} ({member_obj.full_name}): {err_msg}"
            }, status=400)

        # Good standing check
        if not is_member_in_good_standing(member_obj):
            return JsonResponse({
                "ok": False,
                "error": f"Card {idx + 1} ({member_obj.full_name}): Member is not in good standing."
            }, status=400)

        # Bill threshold check
        try:
            bill_value = float(bill_str)
        except ValueError:
            return JsonResponse({
                "ok": False,
                "error": f"Card {idx + 1}: Bill must be a valid number."
            }, status=400)

        threshold = get_accidental_sickness_aid_threshold()
        if bill_value <= threshold:
            return JsonResponse({
                "ok": False,
                "error": f"Card {idx + 1} ({member_obj.full_name}): Bill must exceed ₱{threshold:,.2f} to qualify."
            }, status=400)

        # Create MedicalAid record
        aid = MedicalAid.objects.create(
            member_id_FK=member_obj,
            request_date=request_date,
            requested_amount=str(get_accidental_sickness_aid_benefit()),
            hospital_name=hospital,
            hospital_date=hospital_date or None,
            hospital_bill_amount=bill_str,
            claim_year=req_year,
            document_status=reason,
            policy_record_status="Pending",
            validated_aid_amount=get_accidental_sickness_aid_benefit(),
            status="Pending",
            treasurer_validated_by_user_id_FK=recorded_by,
        )

        TransactionVerification.objects.create(
            table_name="medical_aid",
            record_id=aid.medical_aid_id_PK,
            verification_status="Pending Auditor Review",
        )

        # Attach files for this card
        fi = 0
        while True:
            key = f"med_file_{idx}_{fi}"
            f = request.FILES.get(key)
            if not f or getattr(f, "size", 0) <= 0:
                break
            _link_proof_to_record(f, aid, recorded_by)
            fi += 1

        _record_audit_trail(
            table="medical_aid",
            record_id=aid.medical_aid_id_PK,
            action="CREATED",
            actor=recorded_by,
            new={
                "member": member_obj.full_name,
                "request_date": request_date,
                "requested_amount": str(get_accidental_sickness_aid_benefit()),
                "hospital_name": hospital,
                "hospital_date": hospital_date,
                "hospital_bill_amount": bill_str,
                "status": "Pending",
                "document_status": reason,
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

        created_ids.append(aid.medical_aid_id_PK)

    _broadcast_treasurer("aids")
    return JsonResponse({"ok": True, "aid_ids": created_ids, "count": len(created_ids)})


@require_GET
def treasurer_medical_aid_list(request: HttpRequest):
    """Return MedicalAid records for the Treasurer dashboard."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
                "hospital_date": str(aid.hospital_date) if aid.hospital_date else "",
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
    record_ids = [aid.medical_aid_id_PK for aid in aids]
    _log_sensitive_read(request, "medical_aid", record_ids, "Treasurer viewed medical aid list")

    return JsonResponse({"ok": True, "medical_aids": rows})


# --- Death Aid (Claims) APIs (Treasurer) ---
@require_POST
def treasurer_death_aid_add(request: HttpRequest):
    """Create a DEATH_AID row from the Treasurer death aid claim form."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
    death_source = (request.POST.get("death_source") or "").strip()

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
    if benefit_amount <= 0:
        return JsonResponse(
            {"ok": False, "error": f"Unknown relationship '{death_rel}' — death aid amount is ₱0. Please select a valid relationship from the list."},
            status=400,
        )

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
            disbursement_source=death_source if death_source in ("fund", "direct") else None,
            treasurer_validated_by_user_id_FK=treasurer_user,
            auditor_verified_by_user_id_FK=None,
            president_decided_by_user_id_FK=None,
            released_by_user_id_FK=None,
        )

        TransactionVerification.objects.create(
            table_name="death_aid",
            record_id=death_aid.death_aid_id_PK,
            verification_status="Pending Auditor Review",
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
    # but membership_fee model fields are receipt_number / deposit_reference, etc.
    if table_name == "membership_fee":
        payload_map = {
            "fee_ref": "receipt_number",
            "fee_encoder": "deposit_reference",
            "fee_method": "payment_method",
            "fee_date": "payment_date",
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
        "month": getattr(obj, "month_covered", None) or "N/A",
        "date": str(payment_date) if payment_date is not None else "",
        "method": str(payment_method) if payment_method is not None else "",
        "encoded_by": getattr(getattr(obj, "recorded_by_user_id_FK", None), "full_name", "") or "",
        "payment_status": getattr(obj, "payment_status", None) or "",
        "verification_status": "Pending",
    }


@require_GET
def treasurer_members_list(request):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
def treasurer_member_details(request, member_id):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    member = get_object_or_404(Member, pk=member_id)
    year = timezone.now().year
    expected_dues = get_expected_dues_amount()
    fee_amount = get_membership_fee_amount()

    paid_months = set(
        MonthlyDues.objects.filter(
            member_id_FK=member,
            payment_date__year=year,
        ).values_list("month_covered", flat=True)
    )
    missed_months = []
    for m in range(1, 13):
        key = f"{year}-{m:02d}"
        if key not in paid_months:
            missed_months.append(key)

    outstanding_contributions = Contribution.objects.filter(
        member_id_FK=member,
        status="NOT_PAID",
        aid_tracking_post_id_FK__status="tracking",
    ).select_related("aid_tracking_post_id_FK")

    fee_paid = MembershipFee.objects.filter(
        member_id_FK=member,
    ).exclude(
        payment_status__iexact="unpaid",
    ).exists()

    active_aids = []
    for c in outstanding_contributions:
        post = c.aid_tracking_post_id_FK
        active_aids.append({
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "expected_amount": float(c.expected_amount),
            "paid_amount": float(c.paid_amount),
            "status": c.status,
        })

    return JsonResponse({
        "ok": True,
        "member_id": member.member_id_PK,
        "full_name": member.full_name,
        "employee_id": member.employee_id or "",
        "membership_status": member.membership_status,
        "missed_months": missed_months,
        "membership_fee_paid": fee_paid,
        "expected_dues_amount": expected_dues,
        "membership_fee_amount": fee_amount,
        "active_aid_obligations": active_aids,
    })
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    active_count = Member.objects.filter(membership_status="Active").count()

    return JsonResponse({"ok": True, "active_count": active_count})


@require_GET
def treasurer_records_requiring_revision(request):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    revision_verifications = TransactionVerification.objects.filter(
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED]
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
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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

    old_status = member.membership_status

    for k, v in fields.items():
        setattr(member, k, v)

    if hasattr(member, "full_name") and not (member.full_name or "").strip():
        return JsonResponse({"ok": False, "error": "full_name is required."}, status=400)

    member.save()

    new_status = member.membership_status
    if new_status in ("Permanent", "Temporary") and old_status != new_status:
        has_fee = MembershipFee.objects.filter(member_id_FK=member).exists()
        if not has_fee:
            fee = MembershipFee.objects.create(
                member_id_FK=member,
                receipt_number=f"SYS-TEMP-{int(timezone.now().timestamp())}",
                amount=str(get_membership_fee_amount()),
                payment_date=timezone.now().date(),
                payment_method="Pending",
                payment_status="Pending",
                recorded_by_user_id_FK=resolve_officer_from_session(request),
            )
            TransactionVerification.objects.create(
                table_name="membership_fee",
                record_id=fee.fee_id_PK,
                verification_status="Pending",
            )

    _broadcast_treasurer("members")

    return JsonResponse({"ok": True, "member": {"id": member.member_id_PK, "full_name": member.full_name}})


@require_POST
def treasurer_member_retire(request):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
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


# ==========================================================================
# TREASURER AID TRACKING POSTS
# ==========================================================================

@require_GET
def treasurer_approved_aid_posts(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(is_active=True).select_related(
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
            "status": archive.status if archive else "",
            "amount": str(archive.amount) if archive else "0",
            "finish_status": post.finish_status or "",
            "finish_paid_with_funds": post.finish_paid_with_funds,
            "remaining_balance": max(0, float(post.total_expected) - float(post.total_collected)),
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "created_by": post.created_by_user_id_FK.full_name if post.created_by_user_id_FK else "",
            "has_deduction_sheet": bool(post.deduction_sheet),
            "deduction_batch_reference": post.deduction_batch_reference or "",
            "deduction_payroll_period": post.deduction_payroll_period or "",
            "has_remittance": bool(post.deduction_remitted_amount is not None),
            "deduction_remitted_amount": str(post.deduction_remitted_amount) if post.deduction_remitted_amount is not None else None,
            "deduction_remittance_reference": post.deduction_remittance_reference or "",
            "deduction_remitted_date": post.deduction_remitted_date.isoformat() if post.deduction_remitted_date else None,
        })

    return JsonResponse({"ok": True, "posts": items})


@require_GET
def treasurer_aid_post_members(request: HttpRequest, post_id: int):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    try:
        post = AidTrackingPost.objects.select_related("archive_id_FK").get(
            post_id_PK=post_id
        )
    except AidTrackingPost.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Post not found."}, status=404)

    contributions = Contribution.objects.filter(
        aid_tracking_post_id_FK=post,
    ).select_related("member_id_FK").order_by("member_id_FK__full_name")

    members_data = []
    for c in contributions:
        member = c.member_id_FK
        members_data.append({
            "contribution_id": c.contribution_id_PK,
            "member_id": member.member_id_PK,
            "member_name": member.full_name,
            "employee_id": member.employee_id or "",
            "department": member.department or "",
            "expected_amount": str(c.expected_amount),
            "paid_amount": str(c.paid_amount),
            "payment_date": str(c.payment_date) if c.payment_date else None,
            "status": c.status,
            "is_manually_overridden": c.is_manually_overridden,
            "notes": c.notes,
        })

    return JsonResponse({
        "ok": True,
        "post": {
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "target_month": post.target_month,
            "total_expected": str(post.total_expected),
            "total_collected": str(post.total_collected),
            "has_deduction_sheet": bool(post.deduction_sheet),
            "deduction_batch_reference": post.deduction_batch_reference or "",
            "deduction_payroll_period": post.deduction_payroll_period or "",
            "has_remittance": bool(post.deduction_remitted_amount is not None),
            "deduction_remitted_amount": str(post.deduction_remitted_amount) if post.deduction_remitted_amount is not None else None,
            "deduction_remittance_reference": post.deduction_remittance_reference or "",
            "deduction_remitted_date": post.deduction_remitted_date.isoformat() if post.deduction_remitted_date else None,
        },
        "members": members_data,
    })


def _recalculate_total_collected(post_id: int) -> None:
    total = Contribution.objects.filter(
        aid_tracking_post_id_FK=post_id,
        status__in=["PAID", "RECORDED", "PENDING_VERIFICATION"],
    ).aggregate(total=Sum("paid_amount"))["total"] or 0
    AidTrackingPost.objects.filter(post_id_PK=post_id).update(total_collected=total)


@require_POST
@transaction.atomic
def treasurer_aid_post_member_pay(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    contribution_ids = request.POST.getlist("contribution_id")
    if not contribution_ids:
        return JsonResponse({"ok": False, "error": "Missing contribution_id."}, status=400)

    contributions = Contribution.objects.select_related(
        "aid_tracking_post_id_FK", "member_id_FK"
    ).filter(contribution_id_PK__in=[int(cid) for cid in contribution_ids if cid.strip()])

    if not contributions:
        return JsonResponse({"ok": False, "error": "No valid contributions found."}, status=404)

    post = None
    channel_layer = get_channel_layer()

    for contribution in contributions:
        post = contribution.aid_tracking_post_id_FK

        contribution.paid_amount = contribution.expected_amount
        contribution.payment_date = timezone.now().date()
        contribution.status = "RECORDED"
        contribution.is_manually_overridden = False
        contribution.updated_by_user_id_FK = officer
        contribution.save()

        _record_audit_trail(
            table="contribution",
            record_id=contribution.contribution_id_PK,
            action="PAYMENT_RECORDED",
            actor=officer,
            new={
                "status": "RECORDED",
                "paid_amount": str(contribution.expected_amount),
                "payment_date": str(contribution.payment_date),
                "aid_tracking_post_id": post.post_id_PK,
                "member_id": getattr(contribution.member_id_FK, "member_id_PK", None),
            },
            ip=request.META.get("REMOTE_ADDR"),
            notes="Contribution payment recorded.",
        )

        async_to_sync(channel_layer.group_send)(
            "treasurer_dashboard",
            {
                "type": "contribution_updated",
                "post_id": post.post_id_PK,
                "contribution_id": contribution.contribution_id_PK,
                "member_name": getattr(contribution.member_id_FK, "full_name", ""),
                "status": "RECORDED",
                "paid_amount": float(contribution.expected_amount),
            },
        )
        async_to_sync(channel_layer.group_send)(
            "auditor_dashboard",
            {
                "type": "contribution_updated",
                "post_id": post.post_id_PK,
                "contribution_id": contribution.contribution_id_PK,
                "member_name": getattr(contribution.member_id_FK, "full_name", ""),
                "status": "RECORDED",
                "paid_amount": float(contribution.expected_amount),
            },
        )

    if post:
        _recalculate_total_collected(post.post_id_PK)

    return JsonResponse({"ok": True, "status": "RECORDED", "paid": len(contributions)})


@require_POST
@transaction.atomic
def treasurer_aid_post_member_skip(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    contribution_id = (request.POST.get("contribution_id") or "").strip()
    notes = (request.POST.get("notes") or "").strip()

    if not contribution_id:
        return JsonResponse({"ok": False, "error": "Missing contribution_id."}, status=400)

    try:
        contribution = Contribution.objects.get(contribution_id_PK=int(contribution_id))
    except (ValueError, Contribution.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Contribution not found."}, status=404)

    old_status = contribution.status
    contribution.status = "SKIPPED"
    contribution.is_manually_overridden = True
    contribution.paid_amount = 0
    contribution.notes = notes or contribution.notes
    contribution.updated_by_user_id_FK = officer
    contribution.save()

    _record_audit_trail(
        table="contribution",
        record_id=contribution.contribution_id_PK,
        action="SKIPPED",
        actor=officer,
        old={"status": old_status},
        new={
            "status": "SKIPPED",
            "paid_amount": "0",
            "notes": notes or "",
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=notes or None,
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "treasurer_dashboard",
        {
            "type": "contribution_updated",
            "post_id": contribution.aid_tracking_post_id_FK_id,
            "contribution_id": contribution.contribution_id_PK,
            "member_name": getattr(contribution.member_id_FK, "full_name", ""),
            "status": "SKIPPED",
            "paid_amount": 0,
        },
    )
    async_to_sync(channel_layer.group_send)(
        "auditor_dashboard",
        {
            "type": "contribution_updated",
            "post_id": contribution.aid_tracking_post_id_FK_id,
            "contribution_id": contribution.contribution_id_PK,
            "member_name": getattr(contribution.member_id_FK, "full_name", ""),
            "status": "SKIPPED",
            "paid_amount": 0,
        },
    )

    _recalculate_total_collected(contribution.aid_tracking_post_id_FK_id)

    return JsonResponse({"ok": True, "status": "SKIPPED"})


@require_POST
@transaction.atomic
def treasurer_aid_post_finish(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    skip_remaining = (request.POST.get("skip_remaining") or "").strip().lower() == "true"

    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id), is_active=True)
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Active post not found."}, status=404)

    # Prevent duplicate finish requests regardless of current pending stage
    if post.finish_status in ("pending_approval", "pending_auditor"):
        return JsonResponse({"ok": False, "error": "A finish request is already pending."}, status=400)

    # Route the Treasurer's finish request to the Auditor for verification first
    post.finish_status = "pending_auditor"
    post.finish_skip_remaining = skip_remaining
    post.save(update_fields=["finish_status", "finish_skip_remaining"])

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="FINISH_REQUESTED",
        actor=officer,
        new={
            "finish_status": "pending_auditor",
            "finish_skip_remaining": skip_remaining,
        },
        ip=request.META.get("REMOTE_ADDR"),
    )

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""

    channel_layer = get_channel_layer()
    # include stage so websocket consumers and clients can interpret the target role
    payload = {
        "type": "aid_post_finish_requested",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "stage": "auditor",
    }
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    # Prompt auditor clients to refresh their aids section so the new pending_auditor item appears
    _broadcast_to_group("auditor_dashboard", {"type": "data_changed", "section": "aids"})
    # Also explicitly send a dashboard_refresh to auditor group to ensure clients reload aid lists
    async_to_sync(channel_layer.group_send)("auditor_dashboard", {"type": "dashboard_refresh", "section": "aid_tracking"})
    # Also signal treasurer clients to refresh relevant aids section
    _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})

    return JsonResponse({"ok": True, "message": "Finish request submitted for Auditor verification."})


@require_POST
@transaction.atomic
def treasurer_aid_post_mark_finished(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id), is_active=True)
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Active post not found."}, status=404)

    if post.finish_status and post.finish_status not in ("paid_with_funds",):
        return JsonResponse({"ok": False, "error": "A finish request is already " + post.finish_status + "."}, status=400)

    total = Contribution.objects.filter(aid_tracking_post_id_FK=post).count()
    paid_or_pending = Contribution.objects.filter(
        aid_tracking_post_id_FK=post,
        status__in=["PAID", "RECORDED", "PENDING_VERIFICATION"],
    ).count()
    if total == 0:
        return JsonResponse({"ok": False, "error": "No contributions found for this post."}, status=400)
    if (paid_or_pending / total) < 0.7:
        return JsonResponse({"ok": False, "error": f"At least 70% of members must be PAID (currently {paid_or_pending}/{total})."}, status=400)

    if not post.deduction_sheet:
        return JsonResponse({
            "ok": False,
            "error": "Salary deduction sheet must be uploaded before marking as finished. Please upload the deduction sheet with batch reference and payroll period first.",
        }, status=400)

    post.finish_status = "pending_auditor"
    post.finish_skip_remaining = True
    post.save(update_fields=["finish_status", "finish_skip_remaining"])

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="FINISH_REQUESTED",
        actor=officer,
        new={
            "finish_status": "pending_auditor",
            "finish_skip_remaining": True,
            "paid_ratio": f"{paid_or_pending}/{total}",
            "deduction_batch_reference": post.deduction_batch_reference,
            "deduction_payroll_period": post.deduction_payroll_period,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Finish requested with deduction ref {post.deduction_batch_reference} for period {post.deduction_payroll_period}",
    )

    channel_layer = get_channel_layer()
    payload = {
        "type": "aid_post_finish_requested",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "stage": "auditor",
    }
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
    _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})

    return JsonResponse({"ok": True, "message": "Finish request sent to Auditor for verification."})


@require_POST
@transaction.atomic
def treasurer_aid_post_paid_with_funds(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.select_related("archive_id_FK").get(
            post_id_PK=int(post_id), is_active=True
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Active post not found."}, status=404)

    if post.finish_status in ("paid_with_funds", "pending_auditor", "pending_approval", "pending_president", "approved"):
        return JsonResponse({"ok": False, "error": "A finish or fund request is already in progress for this post."}, status=400)

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else "Unknown"

    post.finish_status = "pending_auditor"
    post.finish_skip_remaining = True
    post.finish_paid_with_funds = True
    post.save(update_fields=["finish_status", "finish_skip_remaining", "finish_paid_with_funds"])

    _record_audit_trail(
        table="aid_tracking_post",
        record_id=post.post_id_PK,
        action="PAID_WITH_FUNDS",
        actor=officer,
        new={
            "finish_status": "pending_auditor",
            "finish_skip_remaining": True,
            "finish_paid_with_funds": True,
        },
        ip=request.META.get("REMOTE_ADDR"),
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "auditor_dashboard",
        {
            "type": "aid_post_finish_requested",
            "post_id": post.post_id_PK,
            "member_name": member_name,
            "stage": "auditor",
        },
    )
    async_to_sync(channel_layer.group_send)(
        "treasurer_dashboard",
        {"type": "data_changed", "section": "aids"},
    )

    _recalculate_total_collected(post.post_id_PK)

    return JsonResponse({"ok": True, "status": "pending_auditor", "message": "Fund disbursement sent to Auditor for verification."})


@require_POST
def treasurer_aid_post_member_notify(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    contribution_id = (request.POST.get("contribution_id") or "").strip()
    if not contribution_id:
        return JsonResponse({"ok": False, "error": "Missing contribution_id."}, status=400)

    try:
        contribution = Contribution.objects.select_related(
            "member_id_FK", "aid_tracking_post_id_FK"
        ).get(contribution_id_PK=int(contribution_id))
    except (ValueError, Contribution.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Contribution not found."}, status=404)

    member = contribution.member_id_FK
    _record_audit_trail(
        table="contribution",
        record_id=contribution.contribution_id_PK,
        action="NOTIFIED",
        actor=officer,
        new={"member": getattr(member, "full_name", str(member.pk))},
        ip=request.META.get("REMOTE_ADDR"),
    )

    return JsonResponse({"ok": True, "message": f"Notification sent to {getattr(member, 'full_name', 'member')}."})


@require_GET
def treasurer_aid_post_history(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(is_active=False).select_related(
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
            "status": archive.status if archive else "",
            "amount": str(archive.amount) if archive else "0",
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "updated_at": post.updated_at.isoformat() if post.updated_at else "",
            "created_by": post.created_by_user_id_FK.full_name if post.created_by_user_id_FK else "",
        })

    return JsonResponse({"ok": True, "posts": items})


# ============================================================================
# PAYROLL BATCH CRUD
# ============================================================================


@require_POST
def treasurer_payroll_batch_create(request: HttpRequest):
    """Create a PayrollBatch with its per-member deductions."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    deductions_data = data.get("deductions", [])
    if not deductions_data:
        return JsonResponse({"ok": False, "error": "At least one deduction required."}, status=400)

    total_amount = sum(d["amount"] for d in deductions_data)

    batch = PayrollBatch.objects.create(
        payroll_period=data.get("payroll_period", ""),
        total_amount=total_amount,
        member_count=len(deductions_data),
        hardcopy_reference=data.get("hardcopy_reference", ""),
        notes=data.get("notes", ""),
        status="Pending",
        recorded_by_user_id_FK=officer,
    )

    ded_records = []
    for d in deductions_data:
        ded = PayrollDeduction.objects.create(
            batch_id_FK=batch,
            member_id_FK_id=d["member_id"],
            amount=d["amount"],
            category=d["category"],
            fund_impact=d.get("fund_impact", "inflow"),
            month_covered=d.get("month_covered", ""),
            aid_tracking_post_id_FK_id=d.get("aid_tracking_post_id"),
            notes=d.get("notes", ""),
        )
        ded_records.append(ded)
        
        # Send deduction email to member if it's an aid contribution
        if d["category"] == "aid_contribution" and ded.member_id_FK and ded.member_id_FK.email:
            try:
                # Get aid tracking post details
                requesting_member_name = "A Fellow Member"
                aid_type = "Aid"
                if ded.aid_tracking_post_id_FK:
                    post = ded.aid_tracking_post_id_FK
                    # Try to get the requesting member from the post's source record
                    if hasattr(post, 'source_id') and post.source_id:
                        try:
                            from core_system.models import MedicalAid, DeathAid
                            if post.aid_type == "medical_aid":
                                aid_record = MedicalAid.objects.filter(medical_aid_id=post.source_id).first()
                            elif post.aid_type == "death_aid":
                                aid_record = DeathAid.objects.filter(death_aid_id=post.source_id).first()
                            else:
                                aid_record = None
                            
                            if aid_record and aid_record.member_id_FK:
                                requesting_member_name = aid_record.member_id_FK.full_name
                        except Exception:
                            pass
                    
                    aid_type_map = {
                        "medical_aid": "Medical Aid",
                        "death_aid": "Death Aid",
                    }
                    aid_type = aid_type_map.get(post.aid_type, "Aid")
                
                send_member_deduction_email(
                    member=ded.member_id_FK,
                    deduction_amount=float(d["amount"]),
                    deduction_type="Aid Contribution",
                    requesting_member_name=requesting_member_name,
                    aid_type=aid_type,
                )
            except Exception as e:
                logger.warning("Failed to send deduction email to member %s: %s", ded.member_id_FK.full_name if ded.member_id_FK else "Unknown", e)

    for f in request.FILES.getlist("files"):
        from core_system.shared_view_utils import _sha256_of_uploaded_file, _compute_row_signature

        file_sha256 = _sha256_of_uploaded_file(f)
        SupportingProof.objects.create(
            content_type=ContentType.objects.get_for_model(PayrollBatch),
            object_id=batch.pk,
            file=f,
            file_name=f.name,
            file_type=f.content_type,
            file_sha256=file_sha256,
            row_signature=_compute_row_signature(file_sha256, batch.pk),
            uploaded_by=officer,
        )

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="CREATED",
        actor=officer,
        new={
            "payroll_period": batch.payroll_period,
            "total_amount": float(total_amount),
            "member_count": len(deductions_data),
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Payroll batch created with {len(deductions_data)} deductions",
    )

    _broadcast_pending_counts()

    return JsonResponse({
        "ok": True,
        "batch_id": batch.pk,
        "total_amount": float(total_amount),
        "deduction_count": len(ded_records),
    })


@require_GET
def treasurer_payroll_batch_list(request: HttpRequest):
    """List all PayrollBatches for the Treasurer dashboard."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    batches = PayrollBatch.objects.select_related(
        "recorded_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
        "president_approved_by_user_id_FK",
    ).all().order_by("-created_at")

    items = []
    for b in batches:
        items.append({
            "batch_id": b.batch_id_PK,
            "payroll_period": b.payroll_period,
            "total_amount": float(b.total_amount),
            "member_count": b.member_count,
            "hardcopy_reference": b.hardcopy_reference or "",
            "status": b.status,
            "recorded_by": b.recorded_by_user_id_FK.full_name if b.recorded_by_user_id_FK else "",
            "recorded_at": b.created_at.isoformat() if b.created_at else "",
            "verified_by": b.auditor_verified_by_user_id_FK.full_name if b.auditor_verified_by_user_id_FK else "",
            "approved_by": b.president_approved_by_user_id_FK.full_name if b.president_approved_by_user_id_FK else "",
        })

    return JsonResponse({"ok": True, "batches": items})


@require_GET
def treasurer_payroll_batch_detail(request: HttpRequest, batch_id: int):
    """Get a single PayrollBatch with all its deductions."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id)
    deductions = PayrollDeduction.objects.filter(batch_id_FK=batch).select_related("member_id_FK")

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
            "aid_tracking_post_id": d.aid_tracking_post_id_FK_id,
            "notes": d.notes or "",
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
            "created_at": batch.created_at.isoformat() if batch.created_at else "",
            "auditor_remarks": batch.auditor_remarks or "",
            "returned_reason": batch.returned_reason or "",
            "president_remarks": batch.president_remarks or "",
        },
        "deductions": ded_list,
    })


@require_POST
def treasurer_payroll_batch_edit(request: HttpRequest, batch_id: int):
    """Edit a PayrollBatch and its deductions (only if Pending or Returned)."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id)
    if batch.status not in ("Pending", "Returned for Revision"):
        return JsonResponse({"ok": False, "error": "Can only edit Pending or Returned batches."}, status=400)

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    deductions_data = data.get("deductions", [])
    total_amount = sum(d["amount"] for d in deductions_data) if deductions_data else 0

    batch.payroll_period = data.get("payroll_period", batch.payroll_period)
    batch.total_amount = total_amount
    batch.member_count = len(deductions_data)
    batch.hardcopy_reference = data.get("hardcopy_reference", batch.hardcopy_reference)
    batch.notes = data.get("notes", batch.notes)
    batch.save(update_fields=[
        "payroll_period", "total_amount", "member_count",
        "hardcopy_reference", "notes",
    ])

    if deductions_data:
        batch.deductions.all().delete()
        for d in deductions_data:
            ded = PayrollDeduction.objects.create(
                batch_id_FK=batch,
                member_id_FK_id=d["member_id"],
                amount=d["amount"],
                category=d["category"],
                fund_impact=d.get("fund_impact", "inflow"),
                month_covered=d.get("month_covered", ""),
                aid_tracking_post_id_FK_id=d.get("aid_tracking_post_id"),
                notes=d.get("notes", ""),
            )
            
            # Send deduction email to member if it's an aid contribution
            if d["category"] == "aid_contribution" and ded.member_id_FK and ded.member_id_FK.email:
                try:
                    # Get aid tracking post details
                    requesting_member_name = "A Fellow Member"
                    aid_type = "Aid"
                    if ded.aid_tracking_post_id_FK:
                        post = ded.aid_tracking_post_id_FK
                        # Try to get the requesting member from the post's source record
                        if hasattr(post, 'source_id') and post.source_id:
                            try:
                                from core_system.models import MedicalAid, DeathAid
                                if post.aid_type == "medical_aid":
                                    aid_record = MedicalAid.objects.filter(medical_aid_id=post.source_id).first()
                                elif post.aid_type == "death_aid":
                                    aid_record = DeathAid.objects.filter(death_aid_id=post.source_id).first()
                                else:
                                    aid_record = None
                                
                                if aid_record and aid_record.member_id_FK:
                                    requesting_member_name = aid_record.member_id_FK.full_name
                            except Exception:
                                pass
                        
                        aid_type_map = {
                            "medical_aid": "Medical Aid",
                            "death_aid": "Death Aid",
                        }
                        aid_type = aid_type_map.get(post.aid_type, "Aid")
                    
                    send_member_deduction_email(
                        member=ded.member_id_FK,
                        deduction_amount=float(d["amount"]),
                        deduction_type="Aid Contribution",
                        requesting_member_name=requesting_member_name,
                        aid_type=aid_type,
                    )
                except Exception as e:
                    logger.warning("Failed to send deduction email to member %s: %s", ded.member_id_FK.full_name if ded.member_id_FK else "Unknown", e)

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="EDITED",
        actor=officer,
        new={"total_amount": float(total_amount), "member_count": len(deductions_data)},
        ip=request.META.get("REMOTE_ADDR"),
    )

    return JsonResponse({"ok": True, "batch_id": batch.pk})


@require_POST
def treasurer_payroll_batch_delete(request: HttpRequest, batch_id: int):
    """Delete a PayrollBatch (only if Pending)."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    batch = get_object_or_404(PayrollBatch, pk=batch_id)
    if batch.status != "Pending":
        return JsonResponse({"ok": False, "error": "Can only delete Pending batches."}, status=400)

    officer = resolve_officer_from_session(request)
    batch.delete()

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch_id,
        action="DELETED",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
    )

    return JsonResponse({"ok": True, "message": "Batch deleted."})


@require_GET
def treasurer_payroll_batch_history(request: HttpRequest, batch_id: int):
    """Get audit trail for a PayrollBatch."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    trails = GlobalAuditTrail.objects.filter(
        table_name="PAYROLL_BATCH",
        record_id=batch_id,
    ).order_by("-timestamp")

    items = []
    for t in trails:
        items.append({
            "action": t.action,
            "actor": t.actor_name,
            "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            "notes": t.notes or "",
            "old_values": t.old_values,
            "new_values": t.new_values,
        })

    return JsonResponse({"ok": True, "history": items})


# ============================================================================
# DEPARTMENT-SEGREGATED VISUALIZATION APIs
# ============================================================================

@require_GET
def treasurer_member_stats_by_department(request: HttpRequest):
    """Return member count and status breakdown per department."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    dept_stats_qs = Member.objects.filter(department__isnull=False).values('department').annotate(
        total=Count('member_id_PK'),
        active=Count('member_id_PK', filter=Q(membership_status='Active')),
        permanent=Count('member_id_PK', filter=Q(membership_status='Permanent')),
        temporary=Count('member_id_PK', filter=Q(membership_status='Temporary')),
        retired=Count('member_id_PK', filter=Q(membership_status='retired')),
    ).order_by('department')

    dept_stats = {row['department']: row for row in dept_stats_qs}

    all_departments = sorted(Member.objects.filter(department__isnull=False).values_list('department', flat=True).distinct())
    departments = []
    for dept_name in all_departments:
        stats = dept_stats.get(dept_name, {})
        departments.append({
            "department": dept_name,
            "total": stats.get('total', 0),
            "active": stats.get('active', 0),
            "permanent": stats.get('permanent', 0),
            "temporary": stats.get('temporary', 0),
            "retired": stats.get('retired', 0),
        })

    unassigned_count = Member.objects.filter(
        Q(department__isnull=True) | Q(department='')
    ).count()

    return JsonResponse({
        "ok": True,
        "departments": departments,
        "unassigned_count": unassigned_count,
    })


@require_GET
def treasurer_payment_tracking_by_department(request: HttpRequest):
    """Return payment tracking metrics per department for the current month."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    current_month = timezone.now().strftime('%Y-%m')

    all_departments = sorted(Member.objects.filter(department__isnull=False).values_list('department', flat=True).distinct())
    dept_totals = dict(
        Member.objects.filter(department__isnull=False).values('department').annotate(
            total=Count('member_id_PK')
        ).values_list('department', 'total')
    )

    dept_dues_paid = dict(
        MonthlyDues.objects.filter(month_covered=current_month).values(
            'member_id_FK__department'
        ).annotate(
            dues_paid=Count('member_id_FK', distinct=True)
        ).values_list('member_id_FK__department', 'dues_paid')
    )

    dept_fees_paid = dict(
        MembershipFee.objects.filter(
            payment_status__in=['Full Payment', 'Partial', 'Pending']
        ).values('member_id_FK__department').annotate(
            fees_paid=Count('member_id_FK', distinct=True)
        ).values_list('member_id_FK__department', 'fees_paid')
    )

    departments = []
    for dept_name in all_departments:
        total = dept_totals.get(dept_name, 0)
        dues_paid = dept_dues_paid.get(dept_name, 0)
        fees_paid = dept_fees_paid.get(dept_name, 0)
        departments.append({
            "department": dept_name,
            "total_members": total,
            "dues_paid_current_month": dues_paid,
            "dues_collection_rate": round((dues_paid / total * 100) if total > 0 else 0, 1),
            "membership_fee_paid": fees_paid,
            "fee_collection_rate": round((fees_paid / total * 100) if total > 0 else 0, 1),
        })

    return JsonResponse({
        "ok": True,
        "current_month": current_month,
        "departments": departments,
    })


@require_GET
def treasurer_financial_summary_by_department(request: HttpRequest):
    """Return financial summary (collections and disbursements) per department for the current year."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    year = timezone.now().year

    dept_data = {}

    dues_qs = MonthlyDues.objects.filter(payment_date__year=year).values(
        'member_id_FK__department'
    ).annotate(total=Sum('amount'))
    for row in dues_qs:
        dept = row['member_id_FK__department'] or 'Unassigned'
        dept_data.setdefault(dept, {})['monthly_dues'] = float(row['total'] or 0)

    fees_qs = MembershipFee.objects.filter(payment_date__year=year).values(
        'member_id_FK__department'
    ).annotate(total=Sum('amount'))
    for row in fees_qs:
        dept = row['member_id_FK__department'] or 'Unassigned'
        dept_data.setdefault(dept, {})['membership_fees'] = float(row['total'] or 0)

    med_qs = MedicalAid.objects.filter(request_date__year=year).values(
        'member_id_FK__department'
    ).annotate(total=Sum('validated_aid_amount'))
    for row in med_qs:
        dept = row['member_id_FK__department'] or 'Unassigned'
        dept_data.setdefault(dept, {})['medical_aid'] = float(row['total'] or 0)

    death_qs = DeathAid.objects.filter(claim_date__year=year).values(
        'member_id_FK__department'
    ).annotate(total=Sum('benefit_amount'))
    for row in death_qs:
        dept = row['member_id_FK__department'] or 'Unassigned'
        dept_data.setdefault(dept, {})['death_aid'] = float(row['total'] or 0)

    all_departments = sorted(Member.objects.filter(department__isnull=False).values_list('department', flat=True).distinct())
    departments = []
    for dept_name in all_departments:
        data = dept_data.get(dept_name, {})
        total_in = data.get('monthly_dues', 0) + data.get('membership_fees', 0)
        total_out = data.get('medical_aid', 0) + data.get('death_aid', 0)
        departments.append({
            "department": dept_name,
            "monthly_dues": data.get('monthly_dues', 0),
            "membership_fees": data.get('membership_fees', 0),
            "medical_aid": data.get('medical_aid', 0),
            "death_aid": data.get('death_aid', 0),
            "total_inflow": total_in,
            "total_outflow": total_out,
            "net_position": total_in - total_out,
        })

    return JsonResponse({
        "ok": True,
        "year": year,
        "departments": departments,
    })


@require_GET
def treasurer_aid_trends_by_department(request: HttpRequest):
    """Return aid request trends per department by month for the current year."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    year = timezone.now().year

    med_trends = MedicalAid.objects.filter(request_date__year=year).annotate(
        month=ExtractMonth('request_date')
    ).values('member_id_FK__department', 'month').annotate(
        count=Count('medical_aid_id_PK'),
        total_amount=Sum('validated_aid_amount')
    )

    death_trends = DeathAid.objects.filter(claim_date__year=year).annotate(
        month=ExtractMonth('claim_date')
    ).values('member_id_FK__department', 'month').annotate(
        count=Count('death_aid_id_PK'),
        total_amount=Sum('benefit_amount')
    )

    dept_months = {}
    for row in med_trends:
        dept = row['member_id_FK__department'] or 'Unassigned'
        month = row['month']
        key = (dept, month)
        dept_months[key] = {
            "department": dept,
            "month": month,
            "medical_aid_count": row['count'],
            "medical_aid_amount": float(row['total_amount'] or 0),
            "death_aid_count": 0,
            "death_aid_amount": 0,
            "total_count": row['count'],
            "total_amount": float(row['total_amount'] or 0),
        }

    for row in death_trends:
        dept = row['member_id_FK__department'] or 'Unassigned'
        month = row['month']
        key = (dept, month)
        if key in dept_months:
            dept_months[key]['death_aid_count'] = row['count']
            dept_months[key]['death_aid_amount'] = float(row['total_amount'] or 0)
            dept_months[key]['total_count'] += row['count']
            dept_months[key]['total_amount'] += float(row['total_amount'] or 0)
        else:
            dept_months[key] = {
                "department": dept,
                "month": month,
                "medical_aid_count": 0,
                "medical_aid_amount": 0,
                "death_aid_count": row['count'],
                "death_aid_amount": float(row['total_amount'] or 0),
                "total_count": row['count'],
                "total_amount": float(row['total_amount'] or 0),
            }

    month_labels = [f"{year}-{m:02d}" for m in range(1, 13)]
    all_departments = sorted(Member.objects.filter(department__isnull=False).values_list('department', flat=True).distinct())

    trends_by_dept = {}
    for dept in all_departments:
        dept_months_for_dept = {k: v for k, v in dept_months.items() if k[0] == dept}
        medical_aid_counts = []
        medical_aid_amounts = []
        death_aid_counts = []
        death_aid_amounts = []
        total_counts = []
        total_amounts = []
        for m in range(1, 13):
            key = (dept, m)
            entry = dept_months_for_dept.get(key, {
                "department": dept,
                "month": m,
                "medical_aid_count": 0,
                "medical_aid_amount": 0,
                "death_aid_count": 0,
                "death_aid_amount": 0,
                "total_count": 0,
                "total_amount": 0,
            })
            medical_aid_counts.append(entry["medical_aid_count"])
            medical_aid_amounts.append(entry["medical_aid_amount"])
            death_aid_counts.append(entry["death_aid_count"])
            death_aid_amounts.append(entry["death_aid_amount"])
            total_counts.append(entry["total_count"])
            total_amounts.append(entry["total_amount"])
        trends_by_dept[dept] = {
            "department": dept,
            "months": month_labels,
            "medical_aid_counts": medical_aid_counts,
            "medical_aid_amounts": medical_aid_amounts,
            "death_aid_counts": death_aid_counts,
            "death_aid_amounts": death_aid_amounts,
            "total_counts": total_counts,
            "total_amounts": total_amounts,
        }

    return JsonResponse({
        "ok": True,
        "year": year,
        "months": month_labels,
        "departments": list(trends_by_dept.values()),
    })


@require_GET
def treasurer_payroll_analysis_by_department(request: HttpRequest):
    """Return payroll deduction analysis per department."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    dept_stats_qs = PayrollDeduction.objects.select_related(
        'member_id_FK'
    ).filter(
        member_id_FK__department__isnull=False
    ).values('member_id_FK__department').annotate(
        total_deductions=Sum('amount'),
        deduction_count=Count('deduction_id_PK'),
    )

    dept_stats = {row['member_id_FK__department']: row for row in dept_stats_qs}

    all_departments = sorted(Member.objects.filter(department__isnull=False).values_list('department', flat=True).distinct())
    departments = []
    for dept_name in all_departments:
        row = dept_stats.get(dept_name, {})
        total_deductions = float(row.get('total_deductions') or 0)
        deduction_count = row.get('deduction_count', 0)
        departments.append({
            "department": dept_name,
            "total_deductions": total_deductions,
            "deduction_count": deduction_count,
            "average_deduction": round(total_deductions / deduction_count, 2) if deduction_count > 0 else 0,
        })

    return JsonResponse({
        "ok": True,
        "departments": departments,
    })


@require_POST
@transaction.atomic
def treasurer_aid_post_release(request: HttpRequest):
    """Treasurer releases the aid payout: records fund in/out and closes the post."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.select_related("archive_id_FK").get(
            post_id_PK=int(post_id), is_active=True, finish_status="pending_release"
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Post not found or not pending release."}, status=404)

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else "Unknown"

    transactions = []

    if post.finish_paid_with_funds:
        # Fund already covered the aid — record outflow for the full expected amount
        transactions.append(
            FundTransaction(
                direction="outflow",
                amount=post.total_expected,
                source_type="aid_post_payment",
                source_id=post.post_id_PK,
                description=f"Fund disbursement — {member_name} ({post.aid_type})",
                recorded_by_user_id_FK=officer,
            )
        )
    else:
        # Record outflow for the total collected amount (aid disbursement to member)
        # (inflow was already recorded at Auditor verify time)
        transactions.append(
            FundTransaction(
                direction="outflow",
                amount=post.total_collected,
                source_type=archive.transaction_type if archive else "aid_post_payment",
                source_id=archive.record_id if archive else post.post_id_PK,
                description=f"Aid disbursement — {member_name} ({post.aid_type})",
                recorded_by_user_id_FK=officer,
            )
        )

    FundTransaction.objects.bulk_create(transactions)

    channel_layer = get_channel_layer()

    if post.finish_paid_with_funds:
        # Mark aid as Released (fund paid the recipient)
        if archive is not None:
            if archive.transaction_type == "death_aid":
                DeathAid.objects.filter(death_aid_id_PK=archive.record_id).update(status="Released")
            elif archive.transaction_type == "medical_aid":
                MedicalAid.objects.filter(medical_aid_id_PK=archive.record_id).update(status="Released")

        # Enter repayment phase — members still owe the fund
        post.finish_status = "repayment"
        post.save(update_fields=["finish_status"])

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_RELEASED",
            actor=officer,
            new={
                "finish_status": "repayment",
                "is_active": True,
                "members_still_owe": float(post.total_expected - post.total_collected),
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

        async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
            "type": "data_changed", "section": "aids",
        })
        async_to_sync(channel_layer.group_send)("auditor_dashboard", {
            "type": "data_changed", "section": "aids",
        })
        async_to_sync(channel_layer.group_send)("president_dashboard", {
            "type": "data_changed", "section": "aids",
        })

        return JsonResponse({"ok": True, "message": "Funds disbursed. Members still owe repayments to replenish the fund.", "status": "repayment"})
    else:
        # Close the post normally
        if archive is not None:
            if archive.transaction_type == "death_aid":
                DeathAid.objects.filter(death_aid_id_PK=archive.record_id).update(status="Released")
            elif archive.transaction_type == "medical_aid":
                MedicalAid.objects.filter(medical_aid_id_PK=archive.record_id).update(status="Released")

        post.finish_status = "approved"
        post.is_active = False
        post.save(update_fields=["finish_status", "is_active"])

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_RELEASED",
            actor=officer,
            new={
                "finish_status": "approved",
                "is_active": False,
                "inflow_count": sum(1 for t in transactions if t.direction == "inflow"),
                "outflow_count": sum(1 for t in transactions if t.direction == "outflow"),
            },
            ip=request.META.get("REMOTE_ADDR"),
        )

        payload = {
            "type": "aid_post_finished",
            "post_id": post.post_id_PK,
            "member_name": member_name,
        }
        async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
        async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
        async_to_sync(channel_layer.group_send)("president_dashboard", payload)

        try:
            _notify_release(post, officer, request=request)
        except Exception:
            logger.exception("Release notification failed for post %s", post.post_id_PK)

        return JsonResponse({"ok": True, "message": "Funds released. Aid post closed."})


@require_POST
def treasurer_aid_post_release_acknowledge(request: HttpRequest, post_id: int):
    guard = require_role(request, role=["Auditor", "President"])
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    try:
        post = AidTrackingPost.objects.select_related("archive_id_FK").get(
            post_id_PK=post_id, is_active=False, finish_status="approved"
        )
    except AidTrackingPost.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Released post not found."}, status=404)

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else "Unknown"
    aid_label = "Medical Aid" if post.aid_type == "medical_aid" else "Death Aid"

    already = GlobalAuditTrail.objects.filter(
        action="RELEASE_ACKNOWLEDGED",
        table_name="AID_TRACKING_POST",
        record_id=post_id,
        actor_id=officer.user_id_PK,
    ).exists()
    if already:
        return JsonResponse({"ok": True, "acknowledged": True})

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post_id,
        action="RELEASE_ACKNOWLEDGED",
        actor=officer,
        new={
            "finish_status": post.finish_status,
            "total_collected": float(post.total_collected),
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f'{officer.role} acknowledged release of {member_name}\'s {aid_label} aid \u2014 \u20b1{post.total_collected:,.2f}',
    )

    return JsonResponse({"ok": True, "acknowledged": True})


@require_POST
@transaction.atomic
def treasurer_aid_post_close_repayment(request: HttpRequest):
    """Close a paid-with-funds post after members have repaid or been skipped."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(
            post_id_PK=int(post_id), finish_status="repayment"
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Repayment post not found."}, status=404)

    # Skip any remaining NOT_PAID contributions
    skipped = Contribution.objects.filter(
        aid_tracking_post_id_FK=post, status="NOT_PAID",
    ).update(
        status="SKIPPED", is_manually_overridden=True, paid_amount=0,
    )

    totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
        total_collected=Sum("paid_amount"),
    )
    post.total_collected = totals["total_collected"] or 0
    post.finish_status = "pending_auditor"
    post.save(update_fields=["finish_status", "total_collected"])

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="REPAYMENT_SUBMITTED_FOR_VERIFICATION",
        actor=officer,
        new={
            "finish_status": "pending_auditor",
            "skipped_count": skipped,
            "total_collected": float(post.total_collected),
        },
        ip=request.META.get("REMOTE_ADDR"),
    )

    member_name = ""
    archive = post.archive_id_FK
    if archive:
        member_name = archive.member_name or ""

    channel_layer = get_channel_layer()
    payload = {
        "type": "aid_post_repayment_pending",
        "post_id": post.post_id_PK,
        "member_name": member_name,
    }
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("president_dashboard", payload)

    return JsonResponse({"ok": True, "message": f"Repayment submitted for verification. {skipped} members skipped. Total collected: ₱{post.total_collected:.2f}"})


@require_POST
@transaction.atomic
def treasurer_aid_post_upload_deduction_sheet(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or request.POST.get("post") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id))
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Post not found."}, status=404)

    sheet_file = request.FILES.get("deduction_sheet")
    batch_reference = (request.POST.get("batch_reference") or "").strip()
    payroll_period = (request.POST.get("payroll_period") or "").strip()

    if not sheet_file:
        return JsonResponse({"ok": False, "error": "Deduction sheet file is required."}, status=400)
    if not batch_reference:
        return JsonResponse({"ok": False, "error": "Batch reference is required."}, status=400)
    if not payroll_period:
        return JsonResponse({"ok": False, "error": "Payroll period is required."}, status=400)

    post.deduction_sheet.save(sheet_file.name, sheet_file, save=False)
    post.deduction_batch_reference = batch_reference
    post.deduction_payroll_period = payroll_period
    post.deduction_sheet_uploaded_at = timezone.now()
    post.save(update_fields=[
        "deduction_sheet",
        "deduction_batch_reference",
        "deduction_payroll_period",
        "deduction_sheet_uploaded_at",
        "updated_at",
    ])

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="DEDUCTION_SHEET_UPLOADED",
        actor=officer,
        new={
            "batch_reference": batch_reference,
            "payroll_period": payroll_period,
            "file_name": sheet_file.name,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Deduction sheet uploaded for post {post.post_id_PK}: ref {batch_reference}, period {payroll_period}",
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "auditor_dashboard",
        {
            "type": "deduction_sheet_uploaded",
            "post_id": post.post_id_PK,
            "batch_reference": batch_reference,
            "payroll_period": payroll_period,
        },
    )

    return JsonResponse({
        "ok": True,
        "message": "Deduction sheet uploaded successfully.",
        "batch_reference": batch_reference,
        "payroll_period": payroll_period,
    })


@require_POST
@transaction.atomic
def treasurer_aid_post_record_remittance(request: HttpRequest):
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or request.POST.get("post") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id))
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Post not found."}, status=404)

    remitted_amount = request.POST.get("remitted_amount", "").strip()
    remittance_reference = request.POST.get("remittance_reference", "").strip()
    remitted_date = request.POST.get("remitted_date", "").strip()

    if not remitted_amount:
        return JsonResponse({"ok": False, "error": "Remitted amount is required."}, status=400)
    if not remittance_reference:
        return JsonResponse({"ok": False, "error": "Remittance reference is required."}, status=400)
    if not remitted_date:
        return JsonResponse({"ok": False, "error": "Remitted date is required."}, status=400)

    try:
        amount = decimal.Decimal(str(remitted_amount))
        if amount <= 0:
            raise ValueError
    except (ValueError, decimal.InvalidOperation):
        return JsonResponse({"ok": False, "error": "Remitted amount must be a positive number."}, status=400)

    from datetime import date as date_type
    try:
        parsed_date = date_type.fromisoformat(remitted_date)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    old_values = {}
    if post.deduction_remitted_amount is not None:
        old_values = {
            "old_remitted_amount": str(post.deduction_remitted_amount),
            "old_remittance_reference": post.deduction_remittance_reference,
            "old_remitted_date": str(post.deduction_remitted_date) if post.deduction_remitted_date else None,
        }

    post.deduction_remitted_amount = amount
    post.deduction_remittance_reference = remittance_reference
    post.deduction_remitted_date = parsed_date
    post.deduction_remitted_at = timezone.now()
    post.save(update_fields=[
        "deduction_remitted_amount",
        "deduction_remittance_reference",
        "deduction_remitted_date",
        "deduction_remitted_at",
        "updated_at",
    ])

    FundTransaction.objects.create(
        direction="inflow",
        amount=amount,
        source_type="salary_deduction_remittance",
        source_id=post.post_id_PK,
        description=f"Salary deduction remittance ref {remittance_reference} for aid post {post.post_id_PK}",
        reference_number=remittance_reference,
        recorded_by_user_id_FK=officer,
    )

    action = "DEDUCTION_REMITTANCE_UPDATED" if old_values else "DEDUCTION_REMITTANCE_RECORDED"
    audit_new = {
        "remitted_amount": str(amount),
        "remittance_reference": remittance_reference,
        "remitted_date": remitted_date,
    }
    audit_kwargs = {
        "table": "AID_TRACKING_POST",
        "record_id": post.post_id_PK,
        "action": action,
        "actor": officer,
        "new": audit_new,
        "ip": request.META.get("REMOTE_ADDR"),
        "notes": f"Remittance {'updated' if old_values else 'recorded'} — ref {remittance_reference}, amount {amount}, date {remitted_date}",
    }
    if old_values:
        audit_kwargs["old"] = old_values
    _record_audit_trail(**audit_kwargs)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "auditor_dashboard",
        {
            "type": "deduction_remittance_recorded",
            "post_id": post.post_id_PK,
            "remitted_amount": str(amount),
            "remittance_reference": remittance_reference,
        },
    )

    return JsonResponse({
        "ok": True,
        "message": "Remittance recorded successfully.",
        "remitted_amount": str(amount),
        "remittance_reference": remittance_reference,
        "remitted_date": remitted_date,
    })


# ==========================================================================
# MEMBER CLAIMS QUEUE — Treasurer Reviews
# ==========================================================================


@require_GET
def treasurer_claims_pending_list(request: HttpRequest):
    """Return pending medical/death aid claims awaiting treasurer review."""
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard

    statuses = ["Pending", "Pending Treasurer Review", "Pending Review"]
    claims = []

    medical_ct = ContentType.objects.get_for_model(MedicalAid)
    for ma in (
        MedicalAid.objects.filter(status__in=statuses)
        .select_related("member_id_FK")
        .order_by("request_date")
    ):
        proof_count = SupportingProof.objects.filter(
            content_type=medical_ct, object_id=ma.medical_aid_id_PK
        ).count()
        claims.append({
            "id": ma.medical_aid_id_PK,
            "claim_type": "medical_aid",
            "status": ma.status,
            "member_name": ma.member_id_FK.full_name,
            "member_employee_id": ma.member_id_FK.employee_id or "",
            "submitted_date": ma.request_date.isoformat(),
            "hospital_name": ma.hospital_name,
            "deceased_name": "",
            "amount": float(ma.requested_amount or ma.hospital_bill_amount or 0),
            "proof_count": proof_count,
        })

    death_ct = ContentType.objects.get_for_model(DeathAid)
    for da in (
        DeathAid.objects.filter(status__in=statuses)
        .select_related("member_id_FK")
        .order_by("claim_date")
    ):
        proof_count = SupportingProof.objects.filter(
            content_type=death_ct, object_id=da.death_aid_id_PK
        ).count()
        claims.append({
            "id": da.death_aid_id_PK,
            "claim_type": "death_aid",
            "status": da.status,
            "member_name": da.member_id_FK.full_name,
            "member_employee_id": da.member_id_FK.employee_id or "",
            "submitted_date": da.claim_date.isoformat(),
            "hospital_name": "",
            "deceased_name": da.deceased_name,
            "amount": float(da.benefit_amount or 0),
            "proof_count": proof_count,
        })

    claims.sort(key=lambda c: c["submitted_date"])

    return JsonResponse({"ok": True, "claims": claims})


@require_POST
def treasurer_claim_review(request: HttpRequest):
    """Treasurer approves, rejects, or returns a member claim."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    try:
        body = json.loads(request.body)
    except (ValueError, AttributeError):
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    claim_type = (body.get("claim_type") or "").strip()
    claim_id = body.get("claim_id")
    decision = (body.get("decision") or "").strip().lower()
    remarks = (body.get("remarks") or "").strip()

    if claim_type not in ("medical_aid", "death_aid"):
        return JsonResponse({"ok": False, "error": "Invalid claim_type."}, status=400)
    if not claim_id:
        return JsonResponse({"ok": False, "error": "claim_id required."}, status=400)
    if decision not in ("approve", "reject", "return"):
        return JsonResponse({"ok": False, "error": "decision must be approve/reject/return."}, status=400)

    Model = MedicalAid if claim_type == "medical_aid" else DeathAid
    try:
        claim = Model.objects.select_related("member_id_FK").get(pk=claim_id)
    except Model.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Claim not found."}, status=404)

    member = claim.member_id_FK

    if decision == "approve":
        claim.status = "Pending Auditor Verification"
        claim.treasurer_validated_by_user_id_FK = officer
        claim.save()

        message = f"Your {claim_type.replace('_', ' ').title()} claim has been approved by the Treasurer and forwarded to the Auditor."
        Notification.objects.create(
            recipient_type="member",
            recipient_id=member.member_id_PK,
            recipient_name=member.full_name,
            notification_type="Claim Update",
            message=message + (f" Remarks: {remarks}" if remarks else ""),
            delivery_status="Sent",
            channel="in_app",
        )
    else:
        set_treasurer_rejected(
            claim_type,
            claim_id,
            officer,
            remarks,
            request,
            member=member,
            is_rejected=(decision == "reject"),
            extra_updates={"treasurer_validated_by_user_id_FK": officer},
            details=(
                f"Your {claim_type.replace('_', ' ').title()} claim was rejected by the Treasurer."
                if decision == "reject"
                else f"Your {claim_type.replace('_', ' ').title()} claim was returned for revision by the Treasurer."
            ),
        )

    _broadcast_treasurer("claims_queue")

    return JsonResponse({"ok": True, "message": "Claim reviewed."})


# ============================================================================
# END TREASURER WORKSPACE VIEWS
# ============================================================================


@require_GET
def treasurer_financial_pending_counts(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    from core_system.constants.status_constants import RegistrationStatus, Status
    from core_system.models import MemberRegistrationRequest, MedicalAid, DeathAid

    registration = MemberRegistrationRequest.objects.filter(
        status__in=[RegistrationStatus.PENDING_TREASURER_REVIEW, RegistrationStatus.RETURNED_FOR_REVISION]
    ).count()

    membership_fees = MembershipFee.objects.filter(payment_status="Pending").count()

    medical_aid = MedicalAid.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()
    death_aid = DeathAid.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()

    return JsonResponse({
        "ok": True,
        "registration": registration,
        "membership_fees": membership_fees,
        "medical_aid": medical_aid,
        "death_aid": death_aid,
        "total": registration + membership_fees + medical_aid + death_aid,
    })
