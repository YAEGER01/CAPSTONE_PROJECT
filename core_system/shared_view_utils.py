import hashlib
import hmac
import json
import re
from typing import Any, Dict, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpRequest

from core_system.constants.policy_constants import (
    get_membership_fee_amount,
    get_monthly_dues_amount,
    is_exempt_from_dues_and_aid,
)
from core_system.models import (
    Member,
    MembershipFee,
    MonthlyDues,
    MedicalAid,
    DeathAid,
    OfficerUser,
    SupportingProof,
    FinancialDocumentArchive,
    AuditFindingsReport,
    TransactionVerification,
    TransactionArchive,
    GlobalAuditTrail,
    SensitiveReadLog,
)

MODEL_MAP = {
    "membership_fee": MembershipFee,
    "monthly_dues": MonthlyDues,
    "medical_aid": MedicalAid,
    "death_aid": DeathAid,
}

UPDATABLE_FIELDS = {
    "membership_fee": ["amount", "payment_method", "payment_status", "month_covered", "payment_date", "receipt_number", "deposit_reference"],
    "monthly_dues": ["month_covered", "amount", "payment_method", "payment_status", "receipt_number", "payment_date", "remittance_reference", "deduction_batch_reference"],
    "medical_aid": ["request_date", "requested_amount", "hospital_name", "hospital_date", "hospital_bill_amount", "document_status", "status", "validated_aid_amount"],
    "death_aid": ["claim_date", "claim_type", "deceased_name", "relationship_to_member", "relationship_group", "benefit_amount", "bill_amount", "document_status", "status"],
}

MONTH_COVERED_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

PAYMENT_ENTITY_TYPE_LABELS = {
    "membership_fee": "MembershipFee",
    "monthly_dues": "MonthlyDues",
}

PAYMENT_SOURCE_LABELS = {
    "membership_fee": "Membership Fee",
    "monthly_dues": "Monthly Dues",
}


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


def resolve_officer_from_session(request) -> Optional["OfficerUser"]:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            return None
    return None


def resolve_member_from_input(member_input: str):
    clean = str(member_input).strip()
    if clean.upper().startswith("M-"):
        clean = clean[2:]
    try:
        pk = int(clean)
    except ValueError:
        return None, JsonResponse(
            {"ok": False, "error": "Member ID must be numeric (e.g., 1) or 'M-<id>'."},
            status=400,
        )
    try:
        return Member.objects.get(member_id_PK=pk), None
    except Member.DoesNotExist:
        return None, JsonResponse({"ok": False, "error": "Member not found."}, status=404)


def check_member_not_retired(member: Member):
    if is_exempt_from_dues_and_aid(member):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from monthly dues per ARTICLE XI Section 2."},
            status=400,
        )
    return None


def _sha256_of_uploaded_file(uploaded_file) -> str:
    sha = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        sha.update(chunk)
    return sha.hexdigest()


def _compute_row_signature(file_digest: str, object_id: int) -> str:
    message = f"{file_digest}:{object_id}:{settings.SECRET_KEY}".encode()
    return hmac.new(
        settings.SECRET_KEY.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()


def _link_proof_to_record(uploaded_file, parent_instance, officer):
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


def _audit_evidence_filename(file_path):
    if not file_path:
        return ""
    return str(file_path).replace("\\", "/").split("/")[-1]


def _get_rejection_info(table_name: str, record_id: int):
    revision = GlobalAuditTrail.objects.filter(
        table_name=table_name,
        record_id=record_id,
        action__in=["RETURNED", "CORRECTION_REQUIRED", "REJECTED"],
    ).order_by("-timestamp").first()
    rejection_reason = revision.notes if revision else ""
    rejection_details = []
    tv = TransactionVerification.objects.filter(
        table_name=table_name, record_id=record_id
    ).first()
    if tv and tv.auditor_remarks:
        try:
            parsed = json.loads(tv.auditor_remarks)
            if isinstance(parsed, dict) and "rejection_details" in parsed:
                rejection_details = parsed["rejection_details"]
        except (json.JSONDecodeError, TypeError):
            pass
    return rejection_reason, rejection_details


def _get_encoder_name(record) -> str:
    encoder_name = ""
    if getattr(record, "recorded_by_user_id_FK", None) is not None:
        encoder_name = getattr(record.recorded_by_user_id_FK, "full_name", None)
        if not encoder_name:
            encoder_name = str(getattr(record.recorded_by_user_id_FK, "user_id_PK",
                                       getattr(record, "recorded_by_user_id_FK_id", "")))
    return encoder_name


def _get_proof_url(content_type_model, object_id) -> str:
    try:
        proof = SupportingProof.objects.filter(
            content_type=ContentType.objects.get_for_model(content_type_model),
            object_id=object_id,
        ).order_by("-uploaded_at").first()
        if proof and getattr(proof, "file", None):
            return proof.file.url
    except Exception:
        pass
    return ""


def _get_auditor_finding_evidence(table_name, record_id):
    archive = FinancialDocumentArchive.objects.filter(
        related_module=str(table_name).upper(),
        related_record_id=int(record_id),
        document_type="auditor_finding",
    ).order_by("-uploaded_at", "-document_id_PK").first()
    return _audit_evidence_filename(getattr(archive, "file_path", "")) if archive else ""


def _get_auditor_verification_remarks(table_name, record_id):
    entity_type = PAYMENT_ENTITY_TYPE_LABELS.get(str(table_name).lower(), str(table_name).title())
    report = AuditFindingsReport.objects.filter(
        report_title=f"Auditor findings: {entity_type} #{record_id}",
    ).order_by("-prepared_date", "-audit_report_id_PK").first()
    remarks = getattr(report, "findings_summary", "") or ""
    if remarks.strip():
        return remarks.strip()
    return "Auditor verified and forwarded to President for final executive sign-off."


def _get_auditor_verification(table_name: str, record_id: int):
    return TransactionVerification.objects.filter(
        table_name=str(table_name).lower(),
        record_id=int(record_id),
    ).order_by("-verified_at").first()


def _serialize_value(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__float__"):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if hasattr(value, "_meta"):
        data = {"id": value.pk}
        if hasattr(value, "full_name"):
            data["name"] = value.full_name
        return data
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value


def _serialize_for_audit(data):
    if not isinstance(data, dict):
        return None
    result = {}
    for key, value in data.items():
        result[key] = _serialize_value(value)
    return result


def _record_audit_trail(
    table,
    record_id,
    action,
    actor,
    old=None,
    new=None,
    ip=None,
    notes=None,
):
    actor_id = None
    actor_name = ""
    actor_type = ""
    if actor is not None:
        actor_id = getattr(actor, "user_id_PK", None)
        actor_name = getattr(actor, "full_name", "") or str(actor)
        actor_type = getattr(actor, "role", "") or ""

    GlobalAuditTrail.objects.create(
        table_name=table,
        record_id=int(record_id),
        action=action,
        old_values=_serialize_for_audit(old),
        new_values=_serialize_for_audit(new),
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        ip_address=ip,
        notes=notes.strip() if isinstance(notes, str) else notes,
    )


def _log_sensitive_read(request, table_name, record_ids, description=""):
    """Log read access to sensitive records.
    - SensitiveReadLog: one entry per record_id
    - GlobalAuditTrail: one summary entry with notes describing the bulk read.
    """
    officer = resolve_officer_from_session(request)
    actor_id = getattr(officer, "user_id_PK", None) if officer else None
    actor_name = getattr(officer, "full_name", "") if officer else ""
    actor_type = getattr(officer, "role", "") if officer else ""
    ip = request.META.get("REMOTE_ADDR")

    batch = [
        SensitiveReadLog(
            table_name=table_name,
            record_id=rid,
            reader_type=actor_type,
            reader_id=actor_id,
            reader_name=actor_name,
            ip_address=ip,
            description=description,
        )
        for rid in record_ids
    ]
    SensitiveReadLog.objects.bulk_create(batch)

    GlobalAuditTrail.objects.create(
        table_name=table_name,
        record_id=0,
        action="READ",
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        ip_address=ip,
        notes=f"{description} ({len(record_ids)} records)",
    )


def _payment_type_label(kind: str, obj: Any) -> str:
    if kind == "monthly_dues":
        method = str(getattr(obj, "payment_method", "") or "").strip()
        if method.lower() == "salary deduction":
            return "Salary Deduction"
    return "OTC Payment"


def _payment_item_to_json(kind: str, obj: Any) -> Dict[str, Any]:
    member = getattr(obj, "member_id_FK", None)
    amount = getattr(obj, "amount", None)
    payment_date = getattr(obj, "payment_date", None)
    payment_method = getattr(obj, "payment_status", None) if kind == "membership_fee" else getattr(obj, "payment_method", None)
    month_covered = getattr(obj, "month_covered", None)
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
        "batch_reference": getattr(obj, "deduction_batch_reference", None) or "",
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


def archive_transaction(table_name, pk, officer=None):
    model = MODEL_MAP.get(table_name)
    if not model:
        return None

    record = model.objects.filter(pk=pk).first()
    if not record:
        return None

    member = getattr(record, "member_id_FK", None)
    member_name = getattr(member, "full_name", "") if member else ""
    member_id = getattr(member, "member_id_PK", None) if member else None

    amount = 0.0
    validated_amount = None
    payment_method = getattr(record, "payment_method", None)
    status = getattr(record, "status", None) or getattr(
        record, "payment_status", "Approved"
    )
    release_reference = getattr(record, "release_reference", None)
    released_by = getattr(record, "released_by_user_id_FK", None)
    verified_at = getattr(record, "request_date", None) or getattr(
        record, "payment_date", None
    )

    if table_name == "membership_fee":
        amount = float(getattr(record, "amount", 0) or 0)
    elif table_name == "monthly_dues":
        amount = float(getattr(record, "amount", 0) or 0)
    elif table_name == "medical_aid":
        amount = float(getattr(record, "validated_aid_amount", 0) or 0)
        validated_amount = amount
    elif table_name == "death_aid":
        amount = float(getattr(record, "benefit_amount", 0) or 0)
        validated_amount = amount

    return TransactionArchive.objects.create(
        transaction_type=table_name,
        record_id=record.pk,
        member_id_FK_id=member_id,
        member_name=member_name,
        amount=amount,
        validated_amount=validated_amount,
        status=status,
        payment_method=payment_method,
        release_reference=release_reference,
        released_by_user_id_FK=released_by,
        verified_at=verified_at,
        archived_by_user_id_FK=officer,
    )


def _broadcast_to_group(group_name: str, message: dict) -> None:
    try:
        async_to_sync(get_channel_layer().group_send)(
            group_name,
            message,
        )
    except Exception:
        pass


def _broadcast_pending_counts(target_groups: Optional[list[str]] = None) -> None:
    from core_system.models import TransactionVerification

    cache.delete_many(["auditor_pending_count", "president_pending_count"])

    auditor_pending = TransactionVerification.objects.filter(
        verification_status="Pending",
        auditor_id_FK__isnull=True,
    ).count()
    cache.set("auditor_pending_count", auditor_pending, 30)

    president_pending = TransactionVerification.objects.filter(
        verification_status="Auditor Verified",
        president_id_FK__isnull=True,
    ).count()
    cache.set("president_pending_count", president_pending, 30)

    if target_groups is None or "auditor_dashboard" in target_groups:
        _broadcast_to_group("auditor_dashboard", {
            "type": "notification_summary",
            "pending_count": auditor_pending,
            "message": f"You have {auditor_pending} pending item(s) for review.",
        })

    if target_groups is None or "president_dashboard" in target_groups:
        _broadcast_to_group("president_dashboard", {
            "type": "notification_summary",
            "pending_count": president_pending,
            "message": f"You have {president_pending} pending item(s) awaiting signature.",
        })

    if target_groups is None or "treasurer_dashboard" in target_groups:
        _broadcast_to_group("treasurer_dashboard", {
            "type": "notification_summary",
            "pending_count": 0,
            "message": "",
        })

    try:
        _send_push_notifications(auditor_pending, president_pending)
    except Exception:
        pass


def _send_push_notifications(auditor_pending: int, president_pending: int) -> None:
    from core_system.models import PushSubscription, OfficerUser
    from pywebpush import webpush

    vapid_private_key = settings.VAPID_PRIVATE_KEY
    vapid_public_key = settings.VAPID_PUBLIC_KEY

    auditor_officers = OfficerUser.objects.filter(role="Auditor").values_list("user_id_PK", flat=True)
    if auditor_pending > 0 and auditor_officers:
        auditor_subs = PushSubscription.objects.filter(officer_id_FK__in=list(auditor_officers))
        payload = json.dumps({
            "title": "Pending Reviews",
            "body": f"You have {auditor_pending} item(s) awaiting review.",
            "url": "/auditor/",
        })
        for sub in auditor_subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        "sub": "mailto:admin@caufa.local",
                        "aud": "https://localhost:5000",
                    },
                )
            except Exception:
                pass

    president_officers = OfficerUser.objects.filter(role="President").values_list("user_id_PK", flat=True)
    if president_pending > 0 and president_officers:
        president_subs = PushSubscription.objects.filter(officer_id_FK__in=list(president_officers))
        payload = json.dumps({
            "title": "Pending Signatures",
            "body": f"You have {president_pending} item(s) awaiting your signature.",
            "url": "/president/",
        })
        for sub in president_subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        "sub": "mailto:admin@caufa.local",
                        "aud": "https://localhost:5000",
                    },
                )
            except Exception:
                pass
