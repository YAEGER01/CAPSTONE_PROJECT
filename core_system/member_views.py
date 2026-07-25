from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from core_system.auth_utils import sha256_hex
from core_system.constants.policy_constants import check_medical_aid_once_per_year
from core_system.constants.status_constants import Status
from core_system.guards import require_officer_session
from core_system.models import (
    AccessSession,
    Claimant,
    Contribution,
    DeathAid,
    MedicalAid,
    Member,
    MemberLedger,
    MembershipFee,
    MonthlyDues,
    Notification,
    OfficerUser,
    SupportingProof,
    TransactionVerification,
)
from core_system.shared_view_utils import _link_proof_to_record

MEMBERSHIP_FEE_SUBMITTED_STATUSES = {"Paid", "Full Payment", "Partial", "Pending"}


def _get_member_from_session(request: HttpRequest) -> tuple[Member | None, str]:
    officer_id = request.session.get("officer_id")
    if not officer_id:
        return None, "No active session"
    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
        member = Member.objects.filter(officer_user_id_FK=officer).first()
        if not member:
            return None, "No linked member profile"
        return member, ""
    except OfficerUser.DoesNotExist:
        return None, "Officer not found"


@require_GET
def member_notifications(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    notifs = Notification.objects.filter(
        recipient_type="member",
        recipient_id=member.member_id_PK,
    ).order_by("-sent_at")[:50]

    items = []
    for n in notifs:
        items.append({
            "id": n.notification_id_PK,
            "type": n.notification_type,
            "message": n.message,
            "category": n.category or "",
            "sent_at": n.sent_at.isoformat() if n.sent_at else "",
            "is_read": n.is_read,
        })

    return JsonResponse({"ok": True, "items": items, "count": len(items)})


@require_GET
def member_ledger(request: HttpRequest):
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    ledger_entries = MemberLedger.objects.filter(
        member_id_FK=member
    ).select_related("recorded_by_user_id_FK").order_by("-recorded_at")

    entries = []
    
    # If no MemberLedger entries exist, fall back to showing MonthlyDues and MembershipFee directly
    if not ledger_entries.exists():
        # Get MonthlyDues - only show fully approved payments
        dues = MonthlyDues.objects.filter(
            member_id_FK=member,
            payment_date__isnull=False,
            payment_status="Full Payment"
        ).order_by("-payment_date")

        for d in dues:
            entries.append({
                "id": f"dues_{d.dues_id_PK}",
                "transaction_type": "monthly_dues",
                "amount": float(d.amount),
                "direction": "credit",
                "balance_after": 0,  # Can't calculate without full ledger history
                "description": f"Monthly Dues - {d.month_covered}",
                "reference_id": d.dues_id_PK,
                "reference_type": "MonthlyDues",
                "recorded_at": d.payment_date.isoformat() if d.payment_date else "",
                "recorded_by": "System",
            })

        # Get MembershipFee - only show fully approved payments
        fees = MembershipFee.objects.filter(
            member_id_FK=member,
            payment_date__isnull=False,
            payment_status__in=["Paid", "Full Payment"]
        ).order_by("-payment_date")

        for f in fees:
            entries.append({
                "id": f"fee_{f.fee_id_PK}",
                "transaction_type": "membership_fee",
                "amount": float(f.amount),
                "direction": "credit",
                "balance_after": 0,  # Can't calculate without full ledger history
                "description": "Membership Fee Payment",
                "reference_id": f.fee_id_PK,
                "reference_type": "MembershipFee",
                "recorded_at": f.payment_date.isoformat() if f.payment_date else "",
                "recorded_by": "System",
            })
        
        # Sort by date
        entries.sort(key=lambda x: x["recorded_at"], reverse=True)
        current_balance = sum(e["amount"] for e in entries if e["direction"] == "credit")
    else:
        # Use MemberLedger entries
        for entry in ledger_entries:
            entries.append({
                "id": entry.ledger_id_PK,
                "transaction_type": entry.transaction_type,
                "amount": float(entry.amount),
                "direction": entry.direction,
                "balance_after": float(entry.balance_after),
                "description": entry.description,
                "reference_id": entry.reference_id,
                "reference_type": entry.reference_type,
                "recorded_at": entry.recorded_at.isoformat() if entry.recorded_at else "",
                "recorded_by": entry.recorded_by_user_id_FK.full_name if entry.recorded_by_user_id_FK else "System",
            })

        # Get current balance
        latest_entry = ledger_entries.first()
        current_balance = float(latest_entry.balance_after) if latest_entry else Decimal("0.00")

    return JsonResponse({
        "ok": True,
        "entries": entries,
        "current_balance": float(current_balance),
    })


@require_GET
def member_unpaid_months(request: HttpRequest):
    """Return list of unpaid months for monthly dues."""
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    # Get member's join date to calculate which months they should have paid
    join_date = member.date_joined
    if not join_date:
        join_date = timezone.now().date() - timedelta(days=365)  # Default to 1 year ago if not set

    current_date = timezone.now().date()

    # Get all paid months
    paid_months = set()
    paid_dues = MonthlyDues.objects.filter(
        member_id_FK=member,
        payment_status="Full Payment"
    ).values_list('month_covered', flat=True)

    for month_str in paid_dues:
        try:
            paid_months.add(month_str)
        except:
            pass

    # Calculate unpaid months from join date to current month
    unpaid_months = []
    current_year = current_date.year
    current_month = current_date.month

    # Start from the month after join date
    start_year = join_date.year
    start_month = join_date.month + 1
    if start_month > 12:
        start_year += 1
        start_month = 1

    # Iterate through months
    year = start_year
    month = start_month

    while (year < current_year) or (year == current_year and month <= current_month):
        month_str = f"{year}-{month:02d}"

        if month_str not in paid_months:
            # Format month for display
            month_name = timezone.datetime(year, month, 1).strftime("%B %Y")
            unpaid_months.append({
                "month": month_str,
                "display_name": month_name,
                "is_overdue": (year < current_year) or (year == current_year and month < current_month)
            })

        month += 1
        if month > 12:
            month = 1
            year += 1

    return JsonResponse({
        "ok": True,
        "unpaid_months": unpaid_months,
        "total_unpaid": len(unpaid_months),
    })


@require_POST
@csrf_exempt
def member_mark_notifications_read(request: HttpRequest):
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    updated = Notification.objects.filter(
        recipient_type="member",
        recipient_id=member.member_id_PK,
        is_read=False,
    ).update(is_read=True)

    return JsonResponse({
        "ok": True,
        "message": f"{updated} notifications marked as read.",
        "updated_count": updated,
    })


@require_GET
def member_attendance_summary(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    return JsonResponse({
        "ok": True,
        "present": 0,
        "late": 0,
        "absent": 0,
        "total_events": 0,
        "attendance_rate": 0,
        "history": [],
        "upcoming_events": [],
        "message": "Attendance tracking module coming soon.",
    })


@require_POST
def member_update_profile(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    allowed_fields = {"contact_number", "email"}
    changed = False
    for field in allowed_fields:
        if field in data:
            setattr(member, field, str(data[field]).strip())
            changed = True
    if changed:
        member.save(update_fields=list(allowed_fields & set(data.keys())))

    return JsonResponse({
        "ok": True,
        "message": "Profile updated successfully.",
    })


@require_POST
def member_submit_payment(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    # Handle both JSON and multipart/form-data (for file uploads)
    content_type = request.content_type or ""
    if "multipart/form-data" in content_type:
        # Handle file upload
        payment_type = str(request.POST.get("payment_type", "")).strip()
        amount = Decimal(str(request.POST.get("amount", "0")))
        payment_method = str(request.POST.get("payment_method", "")).strip()
        reference_number = str(request.POST.get("reference_number", "")).strip()
        uploaded_files = request.FILES.getlist("proof_file")
        transaction_date = str(request.POST.get("transaction_date", "")).strip()
    else:
        # Handle JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
        payment_type = str(data.get("payment_type", "")).strip()
        amount = Decimal(str(data.get("amount", "0")))
        payment_method = str(data.get("payment_method", "")).strip()
        reference_number = str(data.get("reference_number", "")).strip()
        uploaded_files = []
        transaction_date = str(data.get("transaction_date", "")).strip()

    if not payment_type or amount <= 0 or not payment_method:
        return JsonResponse({"ok": False, "error": "Missing required fields: payment_type, amount, payment_method"}, status=400)

    # Find the treasurer user (or use the member's linked officer as recorded_by)
    officer_id = request.session.get("officer_id")
    officer = OfficerUser.objects.get(user_id_PK=officer_id)

    if payment_type == "Membership Fee":
        # Prevent duplicate membership fee submissions if a membership fee record is already present.
        existing_fee = MembershipFee.objects.filter(
            member_id_FK=member,
            payment_status__in=MEMBERSHIP_FEE_SUBMITTED_STATUSES,
        ).exists()
        if existing_fee:
            return JsonResponse({"ok": True, "message": "Membership fee payment has already been submitted. Thank you."})

        fee = MembershipFee.objects.create(
            member_id_FK=member,
            amount=amount,
            payment_method=payment_method,
            payment_status="Pending",
            payment_date=timezone.now().date(),
            receipt_number=reference_number,
            recorded_by_user_id_FK=officer,
            deposit_reference=reference_number,
        )
        # Link proof files if uploaded
        for uploaded_file in uploaded_files:
            _link_proof_to_record(uploaded_file, fee, officer)
    elif payment_type == "Monthly Dues":
        if "multipart/form-data" in content_type:
            month_covered = str(request.POST.get("month_covered", "")).strip()
        else:
            month_covered = str(data.get("month_covered", "")).strip()
        
        # Use current month if not provided
        if not month_covered:
            month_covered = timezone.now().strftime("%Y-%m")
        
        dues = MonthlyDues.objects.create(
            member_id_FK=member,
            month_covered=month_covered,
            amount=amount,
            payment_method=payment_method,
            payment_status="Pending",
            payment_date=timezone.now().date(),
            receipt_number=reference_number,
            recorded_by_user_id_FK=officer,
            treasurer_status="Pending Treasurer Review",
        )
        # Link proof files if uploaded
        for uploaded_file in uploaded_files:
            _link_proof_to_record(uploaded_file, dues, officer)
        # Create TransactionVerification record for the approval workflow
        TransactionVerification.objects.create(
            table_name="MONTHLY_DUES",
            record_id=dues.dues_id_PK,
            target_category="payment",
            verification_status="Pending Treasurer Review",
        )
    else:
        return JsonResponse({"ok": False, "error": f"Unknown payment type: {payment_type}"}, status=400)

    return JsonResponse({
        "ok": True,
        "message": f"{payment_type} payment submitted for verification.",
    })


@require_POST
def member_file_claim(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    claim_type = str(data.get("claim_type", "")).strip()

    # Block filing a new claim only if the same claim type is already pending
    pending_statuses = tuple(Status.ALL_PENDING) + (
        "Pending Review",
        "Pending Treasurer Review",
        "Pending Auditor Verification",
        "Pending President Approval",
    )
    if claim_type == "medical_aid":
        has_pending = MedicalAid.objects.filter(member_id_FK=member, status__in=pending_statuses).exists()
    elif claim_type == "death_aid":
        has_pending = DeathAid.objects.filter(member_id_FK=member, status__in=pending_statuses).exists()
    else:
        return JsonResponse({"ok": False, "error": f"Unknown claim type: {claim_type}"}, status=400)

    if has_pending:
        return JsonResponse({"ok": False, "error": "You already have a pending claim of this type. Please wait until it is processed or rejected."}, status=400)

    if claim_type == "medical_aid":
        hospital_name = str(data.get("hospital_name", "")).strip()
        hospital_address = str(data.get("hospital_address", "")).strip()
        admission_date = str(data.get("admission_date", "")).strip()
        discharge_date = str(data.get("discharge_date", "")).strip()
        hospital_bill = Decimal(str(data.get("hospital_bill_amount", "0")))
        if not hospital_name or hospital_bill <= 0:
            return JsonResponse({"ok": False, "error": "Hospital name and bill amount required."}, status=400)

        adm = None
        dis = None
        if admission_date:
            try:
                from datetime import datetime as dt
                adm = dt.strptime(admission_date, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"ok": False, "error": "Invalid admission_date format."}, status=400)
        if discharge_date:
            try:
                from datetime import datetime as dt
                dis = dt.strptime(discharge_date, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"ok": False, "error": "Invalid discharge_date format."}, status=400)
        if adm and dis and adm > dis:
            return JsonResponse({"ok": False, "error": "Admission date cannot be after discharge date."}, status=400)

        year = timezone.now().year
        err_msg = check_medical_aid_once_per_year(member, year)
        if err_msg:
            return JsonResponse({"ok": False, "error": err_msg}, status=400)

        reason_for_request = str(data.get("reason_for_request", "")).strip()

        claim = MedicalAid.objects.create(
            member_id_FK=member,
            request_date=timezone.now().date(),
            requested_amount=hospital_bill,
            hospital_name=hospital_name,
            hospital_address=hospital_address,
            admission_date=adm,
            discharge_date=dis,
            reason_for_request=reason_for_request,
            hospital_bill_amount=hospital_bill,
            claim_year=timezone.now().year,
            document_status="Pending",
            policy_record_status="Pending",
            validated_aid_amount=0,
            status="Pending",
        )

        return JsonResponse({
            "ok": True,
            "message": "Medical Aid claim submitted successfully.",
            "claim_id": claim.medical_aid_id_PK,
            "claim_type": "medical_aid",
        })

    elif claim_type == "death_aid":
        deceased_name = str(data.get("deceased_name", "")).strip()
        relationship = str(data.get("relationship", "")).strip()
        benefit_amount = Decimal(str(data.get("benefit_amount", "0")))
        funeral_location = str(data.get("funeral_location", "")).strip()
        date_of_death = str(data.get("date_of_death", "")).strip()
        interment_date = str(data.get("interment_date", "")).strip()
        claimant_name = str(data.get("claimant_name", "")).strip()
        claimant_contact = str(data.get("claimant_contact", "")).strip()

        if not deceased_name or not relationship or benefit_amount <= 0:
            return JsonResponse({"ok": False, "error": "Deceased name, relationship, and benefit amount required."}, status=400)

        if not date_of_death:
            return JsonResponse({"ok": False, "error": "Date of death is required for death aid claims."}, status=400)

        death_date = None
        if date_of_death:
            try:
                from datetime import datetime as dt
                death_date = dt.strptime(date_of_death, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"ok": False, "error": "Invalid date_of_death format."}, status=400)

        interment = None
        if interment_date:
            try:
                from datetime import datetime as dt
                interment = dt.strptime(interment_date, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"ok": False, "error": "Invalid interment_date format."}, status=400)

        claimant, _ = Claimant.objects.get_or_create(
            member_id_FK=member,
            full_name=claimant_name or member.full_name,
            defaults={
                "contact_number": claimant_contact,
                "relationship_to_member": relationship,
                "authorization_status": "Pending",
            },
        )

        claim = DeathAid.objects.create(
            member_id_FK=member,
            claimant_id_FK=claimant,
            claim_date=timezone.now().date(),
            claim_type=relationship,
            date_of_death=death_date,
            deceased_name=deceased_name,
            relationship_to_member=relationship,
            funeral_location=funeral_location,
            interment_date=interment,
            benefit_amount=benefit_amount,
            bill_amount=benefit_amount,
            document_status="Pending",
            status="Pending",
        )

        return JsonResponse({
            "ok": True,
            "message": "Death Aid claim submitted successfully.",
            "claim_id": claim.death_aid_id_PK,
            "claim_type": "death_aid",
        })

    else:
        return JsonResponse({"ok": False, "error": f"Unknown claim type: {claim_type}"}, status=400)


@require_POST
def member_claim_upload_proof(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    officer_id = request.session.get("officer_id")
    officer = OfficerUser.objects.get(user_id_PK=officer_id)

    claim_type = str(request.POST.get("claim_type", "")).strip()
    claim_id_str = str(request.POST.get("claim_id", "")).strip()
    uploaded_file = request.FILES.get("file")

    if not claim_type or not claim_id_str or not uploaded_file:
        return JsonResponse({"ok": False, "error": "claim_type, claim_id, and file are required."}, status=400)

    try:
        claim_id = int(claim_id_str)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid claim_id."}, status=400)

    if claim_type == "medical_aid":
        try:
            claim = MedicalAid.objects.get(medical_aid_id_PK=claim_id, member_id_FK=member)
        except MedicalAid.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Medical aid claim not found."}, status=404)
    elif claim_type == "death_aid":
        try:
            claim = DeathAid.objects.get(death_aid_id_PK=claim_id, member_id_FK=member)
        except DeathAid.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Death aid claim not found."}, status=404)
    else:
        return JsonResponse({"ok": False, "error": "claim_type must be 'medical_aid' or 'death_aid'."}, status=400)

    proof = SupportingProof(
        content_object=claim,
        file=uploaded_file,
        file_name=uploaded_file.name,
        file_type=uploaded_file.content_type or "",
        uploaded_by=officer,
    )
    proof.save()

    proof.file_sha256 = proof.compute_file_hash()
    proof.row_signature = proof.compute_row_signature(proof.file_sha256, proof.object_id)
    proof.save(update_fields=["file_sha256", "row_signature"])

    return JsonResponse({
        "ok": True,
        "proof_id": proof.proof_id_PK,
        "file_name": proof.file_name,
        "message": "File uploaded.",
    })


@require_GET
def member_claims_list(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    ma_ct = ContentType.objects.get_for_model(MedicalAid)
    da_ct = ContentType.objects.get_for_model(DeathAid)

    claims = []

    for ma in MedicalAid.objects.filter(member_id_FK=member).order_by("-request_date"):
        proof_count = SupportingProof.objects.filter(
            content_type=ma_ct, object_id=ma.medical_aid_id_PK
        ).count()
        claims.append({
            "id": ma.medical_aid_id_PK,
            "claim_type": "medical_aid",
            "status": ma.status,
            "submitted": ma.request_date.isoformat() if ma.request_date else "",
            "hospital_name": ma.hospital_name,
            "hospital_address": ma.hospital_address or "",
            "admission_date": ma.admission_date.isoformat() if ma.admission_date else "",
            "discharge_date": ma.discharge_date.isoformat() if ma.discharge_date else "",
            "reason_for_request": ma.reason_for_request or "",
            "amount": float(ma.requested_amount or 0),
            "proof_count": proof_count,
        })

    for da in DeathAid.objects.filter(member_id_FK=member).order_by("-claim_date"):
        proof_count = SupportingProof.objects.filter(
            content_type=da_ct, object_id=da.death_aid_id_PK
        ).count()
        claims.append({
            "id": da.death_aid_id_PK,
            "claim_type": "death_aid",
            "status": da.status,
            "submitted": da.claim_date.isoformat() if da.claim_date else "",
            "deceased_name": da.deceased_name,
            "amount": float(da.benefit_amount or 0),
            "proof_count": proof_count,
        })

    claims.sort(key=lambda c: c["submitted"], reverse=True)

    return JsonResponse({"ok": True, "claims": claims})


@require_GET
def member_claim_detail(request: HttpRequest, claim_id: int):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    claim_type = str(request.GET.get("claim_type", "")).strip()
    if claim_type == "medical_aid":
        ma = MedicalAid.objects.filter(medical_aid_id_PK=claim_id, member_id_FK=member).first()
        da = None
    elif claim_type == "death_aid":
        ma = None
        da = DeathAid.objects.filter(death_aid_id_PK=claim_id, member_id_FK=member).first()
    else:
        try:
            ma = MedicalAid.objects.get(medical_aid_id_PK=claim_id, member_id_FK=member)
        except MedicalAid.DoesNotExist:
            ma = None
        da = None

    if ma is not None:
        ct = ContentType.objects.get_for_model(MedicalAid)
        proofs = SupportingProof.objects.filter(content_type=ct, object_id=ma.medical_aid_id_PK).order_by("-uploaded_at")
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
            "claim": {
                "id": ma.medical_aid_id_PK,
                "claim_type": "medical_aid",
                "status": ma.status,
                "submitted": ma.request_date.isoformat() if ma.request_date else "",
                "hospital_name": ma.hospital_name,
                "hospital_address": ma.hospital_address or "",
                "admission_date": ma.admission_date.isoformat() if ma.admission_date else "",
                "discharge_date": ma.discharge_date.isoformat() if ma.discharge_date else "",
                "reason_for_request": ma.reason_for_request or "",
                "requested_amount": float(ma.requested_amount or 0),
                "hospital_bill_amount": float(ma.hospital_bill_amount or 0),
                "validated_amount": float(ma.validated_aid_amount or 0),
                "treasurer_validated_by": ma.treasurer_validated_by_user_id_FK.full_name if ma.treasurer_validated_by_user_id_FK else "",
                "auditor_verified_by": ma.auditor_verified_by_user_id_FK.full_name if ma.auditor_verified_by_user_id_FK else "",
                "president_decision": ma.president_decision or "",
                "supporting_proofs": supporting_proofs,
            },
        })

    try:
        da = DeathAid.objects.get(death_aid_id_PK=claim_id, member_id_FK=member)
    except DeathAid.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Claim not found."}, status=404)

    ct = ContentType.objects.get_for_model(DeathAid)
    proofs = SupportingProof.objects.filter(content_type=ct, object_id=da.death_aid_id_PK).order_by("-uploaded_at")
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
        "claim": {
            "id": da.death_aid_id_PK,
            "claim_type": "death_aid",
            "status": da.status,
            "submitted": da.claim_date.isoformat() if da.claim_date else "",
            "date_of_death": da.date_of_death.isoformat() if da.date_of_death else "",
            "deceased_name": da.deceased_name,
            "relationship_to_member": da.relationship_to_member,
            "relationship": da.relationship_to_member,
            "benefit_amount": float(da.benefit_amount or 0),
            "bill_amount": float(da.bill_amount or 0),
            "funeral_location": da.funeral_location,
            "interment_date": da.interment_date.isoformat() if da.interment_date else "",
            "death_claim_type": da.claim_type,
            "treasurer_validated_by": da.treasurer_validated_by_user_id_FK.full_name if da.treasurer_validated_by_user_id_FK else "",
            "auditor_verified_by": da.auditor_verified_by_user_id_FK.full_name if da.auditor_verified_by_user_id_FK else "",
            "president_decision": da.president_decision or "",
            "supporting_proofs": supporting_proofs,
        },
    })


@require_POST
def member_save_pin(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    pin = str(data.get("pin", "")).strip()
    current_pin = str(data.get("current_pin", "")).strip()
    if len(pin) != 6 or not pin.isdigit():
        return JsonResponse({"ok": False, "error": "PIN must be exactly 6 digits."}, status=400)
    if member.pin_code:
        if len(current_pin) != 6 or not current_pin.isdigit():
            return JsonResponse({"ok": False, "error": "Current PIN is required and must be 6 digits."}, status=400)
        if sha256_hex(current_pin) != member.pin_code:
            return JsonResponse({"ok": False, "error": "Current PIN is incorrect."}, status=400)
    member.pin_code = sha256_hex(pin)
    member.save(update_fields=["pin_code"])
    return JsonResponse({"ok": True, "message": "Attendance PIN saved successfully."})


@require_POST
def member_save_rep(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    full_name = str(data.get("full_name", "")).strip()
    relationship = str(data.get("relationship", "")).strip()
    contact = str(data.get("contact_number", "")).strip()

    if not full_name or not relationship:
        return JsonResponse({"ok": False, "error": "Name and relationship required."}, status=400)

    Claimant.objects.update_or_create(
        member_id_FK=member,
        full_name=full_name,
        defaults={
            "contact_number": contact,
            "relationship_to_member": relationship,
            "authorization_status": "Active",
        },
    )

    return JsonResponse({
        "ok": True,
        "message": "Authorized representative saved.",
    })


@require_GET
def member_dashboard_data(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    member_data = {
        "member_id": member.member_id_PK,
        "full_name": member.full_name,
        "employee_id": member.employee_id or "",
        "email": member.email or "",
        "contact_number": member.contact_number or "",
        "department": member.department or "",
        "position": member.position or "",
        "employment_status": member.employment_status,
        "membership_status": member.membership_status,
        "member_type": member.member_type,
        "date_joined": member.date_joined.isoformat() if member.date_joined else "",
        "profile_picture": member.profile_picture.url if member.profile_picture else "",
        "pin_code": member.pin_code or "",
        "qr_code": member.qr_code.url if member.qr_code else "",
        "emergency_contact": member.emergency_contact or "",
        "emergency_number": member.emergency_number or "",
    }

    fee = MembershipFee.objects.filter(member_id_FK=member).order_by("-payment_date").first()
    membership_fee_status = fee.payment_status if fee else "Unpaid"
    membership_fee_amount = float(fee.amount) if fee else 0
    membership_fee_paid = fee.payment_status in ("Paid", "Full Payment") if fee else False
    membership_fee_submitted = fee.payment_status in MEMBERSHIP_FEE_SUBMITTED_STATUSES if fee else False

    all_dues = MonthlyDues.objects.filter(member_id_FK=member).order_by("-month_covered")
    total_dues_paid = float(all_dues.filter(payment_status="Paid").aggregate(t=Sum("amount"))["t"] or 0)
    total_dues_pending = float(all_dues.filter(payment_status="Pending").aggregate(t=Sum("amount"))["t"] or 0)
    total_dues_unpaid = float(all_dues.filter(payment_status="Unpaid").aggregate(t=Sum("amount"))["t"] or 0)
    dues_records = []
    for d in all_dues:
        dues_records.append({
            "dues_id": d.dues_id_PK,
            "month_covered": d.month_covered,
            "amount": float(d.amount),
            "payment_status": d.payment_status,
            "payment_method": d.payment_method,
            "payment_date": d.payment_date.isoformat() if d.payment_date else "",
        })

    medical_claim_ids = MedicalAid.objects.filter(member_id_FK=member).values_list("medical_aid_id_PK", flat=True)
    death_claim_ids = DeathAid.objects.filter(member_id_FK=member).values_list("death_aid_id_PK", flat=True)
    contribs = Contribution.objects.filter(member_id_FK=member).exclude(
        Q(aid_tracking_post_id_FK__source_type="medical_aid", aid_tracking_post_id_FK__source_id__in=medical_claim_ids)
        | Q(aid_tracking_post_id_FK__source_type="death_aid", aid_tracking_post_id_FK__source_id__in=death_claim_ids)
    ).select_related("aid_tracking_post_id_FK").order_by("-aid_tracking_post_id_FK__created_at")
    total_contributions = float(contribs.aggregate(t=Sum("paid_amount"))["t"] or 0)
    contribution_records = []
    for c in contribs:
        post = c.aid_tracking_post_id_FK
        contribution_records.append({
            "contribution_id": c.contribution_id_PK,
            "aid_type": post.aid_type if post else "",
            "target_month": post.target_month if post else "",
            "expected_amount": float(c.expected_amount),
            "paid_amount": float(c.paid_amount),
            "payment_date": c.payment_date.isoformat() if c.payment_date else "",
            "status": c.status,
        })

    medical_aid_records = []
    medical_aid_pending = 0
    medical_aid_approved = 0
    medical_aid_released = 0
    for ma in MedicalAid.objects.filter(member_id_FK=member).order_by("-request_date"):
        record = {
            "medical_aid_id": ma.medical_aid_id_PK,
            "request_date": ma.request_date.isoformat() if ma.request_date else "",
            "requested_amount": float(ma.requested_amount or 0),
            "hospital_name": ma.hospital_name,
            "hospital_address": ma.hospital_address or "",
            "admission_date": ma.admission_date.isoformat() if ma.admission_date else "",
            "discharge_date": ma.discharge_date.isoformat() if ma.discharge_date else "",
            "reason_for_request": ma.reason_for_request or "",
            "hospital_bill_amount": float(ma.hospital_bill_amount or 0),
            "validated_aid_amount": float(ma.validated_aid_amount),
            "status": ma.status,
        }
        medical_aid_records.append(record)
        if ma.status in ("Pending", "Pending Review", "Pending Treasurer Review", "Pending Auditor Verification", "Pending President Approval"):
            medical_aid_pending += 1
        elif ma.status in ("Approved", "Verified"):
            medical_aid_approved += 1
        elif ma.status in ("Released", "Completed"):
            medical_aid_released += 1

    death_aid_records = []
    death_aid_pending = 0
    death_aid_approved = 0
    death_aid_released = 0
    for da in DeathAid.objects.filter(member_id_FK=member).order_by("-claim_date"):
        death_aid_records.append({
            "death_aid_id": da.death_aid_id_PK,
            "claim_date": da.claim_date.isoformat() if da.claim_date else "",
            "claim_type": da.claim_type,
            "deceased_name": da.deceased_name,
            "benefit_amount": float(da.benefit_amount),
            "status": da.status,
        })
        if da.status in ("Pending", "Pending Review", "Pending Treasurer Review", "Pending Auditor Verification", "Pending President Approval"):
            death_aid_pending += 1
        elif da.status in ("Approved", "Verified"):
            death_aid_approved += 1
        elif da.status in ("Released", "Completed"):
            death_aid_released += 1

    total_claims = len(medical_aid_records) + len(death_aid_records)

    # Determine if there's an active pending claim with full details for dashboard review
    pending_claim = None
    pending_statuses = tuple(Status.ALL_PENDING) + (
        "Pending Review",
        "Pending Treasurer Review",
        "Pending Auditor Verification",
        "Pending President Approval",
    )
    ma_pending = MedicalAid.objects.filter(member_id_FK=member, status__in=pending_statuses).order_by("-request_date").first()
    if ma_pending:
        pending_claim = {
            "id": ma_pending.medical_aid_id_PK,
            "claim_type": "medical_aid",
            "status": ma_pending.status,
            "hospital_name": ma_pending.hospital_name,
            "hospital_address": ma_pending.hospital_address or "",
            "admission_date": ma_pending.admission_date.isoformat() if ma_pending.admission_date else "",
            "discharge_date": ma_pending.discharge_date.isoformat() if ma_pending.discharge_date else "",
            "reason_for_request": ma_pending.reason_for_request or "",
            "requested_amount": float(ma_pending.requested_amount or 0),
        }
    da_pending = DeathAid.objects.filter(member_id_FK=member, status__in=pending_statuses).order_by("-claim_date").first()
    pending_medical_claim = ma_pending is not None
    pending_death_claim = da_pending is not None
    pending_medical_claim_data = None
    pending_death_claim_data = None
    if ma_pending:
        pending_medical_claim_data = {
            "id": ma_pending.medical_aid_id_PK,
            "claim_type": "medical_aid",
            "status": ma_pending.status,
            "hospital_name": ma_pending.hospital_name,
            "hospital_address": ma_pending.hospital_address or "",
            "admission_date": ma_pending.admission_date.isoformat() if ma_pending.admission_date else "",
            "discharge_date": ma_pending.discharge_date.isoformat() if ma_pending.discharge_date else "",
            "reason_for_request": ma_pending.reason_for_request or "",
            "requested_amount": float(ma_pending.requested_amount or 0),
        }
    if not pending_claim and da_pending:
        pending_claim = {
            "id": da_pending.death_aid_id_PK,
            "claim_type": "death_aid",
            "status": da_pending.status,
            "deceased_name": da_pending.deceased_name,
            "date_of_death": da_pending.claim_date.isoformat() if da_pending.claim_date else "",
            "funeral_location": da_pending.funeral_location or "",
            "benefit_amount": float(da_pending.benefit_amount or 0),
        }
    if da_pending:
        pending_death_claim_data = {
            "id": da_pending.death_aid_id_PK,
            "claim_type": "death_aid",
            "status": da_pending.status,
            "deceased_name": da_pending.deceased_name,
            "date_of_death": da_pending.claim_date.isoformat() if da_pending.claim_date else "",
            "funeral_location": da_pending.funeral_location or "",
            "benefit_amount": float(da_pending.benefit_amount or 0),
        }

    notifs = Notification.objects.filter(recipient_type="member", recipient_id=member.member_id_PK).order_by("-sent_at")[:20]
    notifications = []
    for n in notifs:
        notifications.append({
            "notification_id": n.notification_id_PK,
            "notification_type": n.notification_type,
            "message": n.message,
            "category": n.category or "",
            "sent_at": n.sent_at.isoformat() if n.sent_at else "",
        })

    payment_history = []
    for f in MembershipFee.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date")[:10]:
        payment_history.append({
            "type": "Membership Fee",
            "amount": float(f.amount),
            "method": f.payment_method,
            "status": f.payment_status,
            "date": f.payment_date.isoformat() if f.payment_date else "",
            "reference": f.receipt_number or "",
            "treasurer_status": getattr(f, 'treasurer_status', ''),
            "auditor_status": getattr(f, 'auditor_status', ''),
            "president_status": getattr(f, 'president_status', ''),
        })
    for d in MonthlyDues.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date")[:10]:
        payment_history.append({
            "type": f"Dues ({d.month_covered})",
            "amount": float(d.amount),
            "method": d.payment_method,
            "status": d.payment_status,
            "date": d.payment_date.isoformat() if d.payment_date else "",
            "reference": d.receipt_number or "",
        })
    payment_history.sort(key=lambda x: x["date"], reverse=True)

    member_since_date = ""
    member_since_label = ""
    if member.date_joined:
        member_since_date = member.date_joined.isoformat()
        member_since_label = member.date_joined.strftime("%b %Y")
    else:
        earliest = None
        first_fee = MembershipFee.objects.filter(member_id_FK=member).order_by("payment_date").first()
        if first_fee and first_fee.payment_date:
            earliest = first_fee.payment_date
        first_dues = MonthlyDues.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("payment_date").first()
        if first_dues and first_dues.payment_date:
            if earliest is None or first_dues.payment_date < earliest:
                earliest = first_dues.payment_date
        if earliest:
            member_since_date = earliest.isoformat()
            member_since_label = earliest.strftime("%b %Y")
        else:
            member_since_label = "N/A"

    rep = Claimant.objects.filter(member_id_FK=member).first()
    rep_data = None
    if rep:
        rep_data = {
            "full_name": rep.full_name,
            "contact_number": rep.contact_number or "",
            "relationship": rep.relationship_to_member,
        }

    latest_payment_date = ""
    first_payment_method = ""
    last_pmt = MonthlyDues.objects.filter(member_id_FK=member).order_by("-payment_date").first()
    if last_pmt:
        first_payment_method = last_pmt.payment_method or ""
    if not first_payment_method:
        last_fee = MembershipFee.objects.filter(member_id_FK=member).order_by("-payment_date").first()
        if last_fee:
            first_payment_method = last_fee.payment_method or ""
    last_dues = MonthlyDues.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date").first()
    if last_dues:
        latest_payment_date = last_dues.payment_date.isoformat() if last_dues.payment_date else ""
    today = date.today()
    next_m = today.replace(day=1) + timedelta(days=32)
    next_m = next_m.replace(day=1)
    next_month_str = next_m.strftime("%Y-%m")
    has_next = MonthlyDues.objects.filter(member_id_FK=member, month_covered=next_month_str).exists()
    next_due_date = next_m.strftime("%b %d") if not has_next else ""

    total_claims = len(medical_aid_records) + len(death_aid_records)
    total_financial_contributions = membership_fee_amount + total_dues_paid + total_contributions
    total_paid = membership_fee_amount + total_dues_paid
    pending_amount = total_dues_pending

    rep = Claimant.objects.filter(member_id_FK=member).first()

    return JsonResponse({
        "ok": True,
        "member_data": member_data,
        "membership_fee_status": membership_fee_status,
        "membership_fee_amount": membership_fee_amount,
        "membership_fee_paid": membership_fee_paid,
        "membership_fee_submitted": membership_fee_submitted,
        "total_dues_paid": total_dues_paid,
        "total_dues_pending": total_dues_pending,
        "total_dues_unpaid": total_dues_unpaid,
        "outstanding_balance": total_dues_unpaid,
        "total_contributions": total_contributions,
        "total_financial_contributions": total_financial_contributions,
        "total_paid": total_paid,
        "pending_amount": pending_amount,
        "next_due_date": next_due_date,
        "latest_payment_date": latest_payment_date,
        "first_payment_method": first_payment_method,
        "total_claims": total_claims,
        "dues_records": dues_records,
        "contribution_records": contribution_records,
        "medical_aid_records": medical_aid_records,
        "death_aid_records": death_aid_records,
        "notifications": notifications,
        "payment_history": payment_history,
        "rep_data": rep_data,
        "member_since_date": member_since_date,
        "member_since_label": member_since_label,
        "medical_aid_pending": medical_aid_pending,
        "medical_aid_approved": medical_aid_approved,
        "medical_aid_released": medical_aid_released,
        "death_aid_pending": death_aid_pending,
        "death_aid_approved": death_aid_approved,
        "death_aid_released": death_aid_released,
        "pending_claim": pending_claim,
        "pending_medical_claim": pending_medical_claim,
        "pending_death_claim": pending_death_claim,
        "pending_medical_claim_data": pending_medical_claim_data,
        "pending_death_claim_data": pending_death_claim_data,
    })


@require_POST
def member_upload_picture(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)

    file = request.FILES.get("profile_picture")
    if not file:
        return JsonResponse({"ok": False, "error": "No file provided."}, status=400)

    # Validate file type
    allowed = ("image/jpeg", "image/png", "image/webp", "image/gif")
    if file.content_type not in allowed:
        return JsonResponse({"ok": False, "error": "Only JPG, PNG, WebP, GIF allowed."}, status=400)

    member.profile_picture = file
    member.save(update_fields=["profile_picture"])
    return JsonResponse({
        "ok": True,
        "url": member.profile_picture.url,
        "message": "Profile picture updated.",
    })


@require_POST
def onboarding_upload_photo(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)
    file = request.FILES.get("profile_picture")
    if not file:
        return JsonResponse({"ok": False, "error": "No file provided."}, status=400)
    member.profile_picture = file
    member.save(update_fields=["profile_picture"])
    return JsonResponse({"ok": True, "url": member.profile_picture.url})


@require_POST
def onboarding_save_qr(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)
    current_pin = str(request.POST.get("current_pin", "")).strip()
    if member.pin_code:
        if len(current_pin) != 6 or not current_pin.isdigit():
            return JsonResponse({"ok": False, "error": "Current PIN is required and must be 6 digits."}, status=400)
        if sha256_hex(current_pin) != member.pin_code:
            return JsonResponse({"ok": False, "error": "Current PIN is incorrect."}, status=400)
    file = request.FILES.get("qr_code")
    if not file:
        return JsonResponse({"ok": False, "error": "No QR code file provided."}, status=400)
    member.qr_code = file
    member.save(update_fields=["qr_code"])
    return JsonResponse({"ok": True, "url": member.qr_code.url})


@require_POST
def onboarding_save_pin(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    pin = str(data.get("pin", "")).strip()
    current_pin = str(data.get("current_pin", "")).strip()
    if len(pin) != 6 or not pin.isdigit():
        return JsonResponse({"ok": False, "error": "PIN must be exactly 6 digits."}, status=400)
    if member.pin_code:
        if len(current_pin) != 6 or not current_pin.isdigit():
            return JsonResponse({"ok": False, "error": "Current PIN is required and must be 6 digits."}, status=400)
        if sha256_hex(current_pin) != member.pin_code:
            return JsonResponse({"ok": False, "error": "Current PIN is incorrect."}, status=400)
    member.pin_code = sha256_hex(pin)
    member.save(update_fields=["pin_code"])
    return JsonResponse({"ok": True})


@require_POST
def onboarding_complete(request: HttpRequest):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    member, err = _get_member_from_session(request)
    if not member:
        return JsonResponse({"ok": False, "error": err}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    member.contact_number = str(data.get("contact_number", member.contact_number or "")).strip()
    member.emergency_contact = str(data.get("emergency_contact", "")).strip()
    member.emergency_number = str(data.get("emergency_number", "")).strip()
    member.setup_complete = True
    member.save(update_fields=["contact_number", "emergency_contact", "emergency_number", "setup_complete"])
    return JsonResponse({"ok": True, "message": "Onboarding complete!"})
