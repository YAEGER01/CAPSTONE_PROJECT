import hashlib
import hmac
import json
import logging
import re
import threading
from typing import Any, Dict, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

VAPID_CONTACT = getattr(settings, "VAPID_CONTACT", "mailto:admin@caufa.local")
VAPID_ORIGIN = getattr(settings, "VAPID_ORIGIN", "http://127.0.0.1:8000")
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from core_system.guards import require_role
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

from core_system.constants.status_constants import Status
from core_system.constants.policy_constants import (
    get_membership_fee_amount,
    get_monthly_dues_amount,
    is_exempt_from_dues_and_aid,
)
from core_system.models import (
    AuditFindingsReport,
    Contribution,
    DeathAid,
    FinancialDocumentArchive,
    GlobalAuditTrail,
    MedicalAid,
    Member,
    MembershipFee,
    MonthlyDues,
    OfficerUser,
    PayrollBatch,
    SensitiveReadLog,
    SupportingProof,
    TransactionArchive,
    TransactionVerification,
)

MODEL_MAP = {
    "membership_fee": MembershipFee,
    "monthly_dues": MonthlyDues,
    "medical_aid": MedicalAid,
    "death_aid": DeathAid,
    "payroll_batch": PayrollBatch,
    "contribution": Contribution,
}

UPDATABLE_FIELDS = {
    "membership_fee": ["amount", "payment_method", "payment_status", "payment_date", "receipt_number", "deposit_reference"],
    "monthly_dues": ["month_covered", "amount", "payment_method", "payment_status", "receipt_number", "payment_date", "remittance_reference", "deduction_batch_reference"],
    "medical_aid": ["request_date", "requested_amount", "reason", "hospital_name", "hospital_date", "hospital_bill_amount", "document_status"],
    "death_aid": ["claim_date", "claim_type", "deceased_name", "relationship_to_member", "relationship_group", "bill_amount", "document_status"],
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
        logger.exception("Failed to get proof URL for %s id=%s", content_type_model, object_id)
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


def _compute_entry_hash(
    previous_hash, table, record_id, action, old_str, new_str, timestamp_str
):
    chain_str = f"{previous_hash}:{table}:{record_id}:{action}:{old_str}:{new_str}:{timestamp_str}"
    entry_hash = hashlib.sha256(chain_str.encode()).hexdigest()
    hmac_sig = hmac.new(
        settings.SECRET_KEY.encode(),
        entry_hash.encode(),
        hashlib.sha256,
    ).hexdigest()
    return entry_hash, hmac_sig


def _record_audit_trail(
    table,
    record_id,
    action,
    actor,
    old=None,
    new=None,
    ip=None,
    device_info=None,
    notes=None,
    actor_type_override=None,
    actor_name_override=None,
):
    actor_id = None
    actor_name = ""
    actor_type = ""
    if actor is not None:
        actor_id = getattr(actor, "user_id_PK", None)
        actor_name = actor_name_override or getattr(actor, "full_name", "") or str(actor)
        actor_type = actor_type_override or getattr(actor, "role", "") or ""

    latest = GlobalAuditTrail.objects.order_by("-trail_id").first()
    previous_hash = latest.entry_hash if (latest and latest.entry_hash) else "0" * 64

    old_serialized = _serialize_for_audit(old)
    new_serialized = _serialize_for_audit(new)

    entry = GlobalAuditTrail.objects.create(
        table_name=table,
        record_id=int(record_id),
        action=action,
        old_values=old_serialized,
        new_values=new_serialized,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        ip_address=ip,
        device_info=device_info,
        notes=notes.strip() if isinstance(notes, str) else notes,
        previous_hash=previous_hash,
    )

    old_str = json.dumps(old_serialized, sort_keys=True) if old_serialized else ""
    new_str = json.dumps(new_serialized, sort_keys=True) if new_serialized else ""
    timestamp_str = entry.timestamp.isoformat()

    entry.entry_hash, entry.hmac_signature = _compute_entry_hash(
        previous_hash, table, record_id, action, old_str, new_str, timestamp_str
    )
    entry.save(update_fields=["entry_hash", "hmac_signature"])


def _record_bulk_audit_trail(entries, actor):
    """Bulk-create audit entries with hash-chain integrity.

    `entries` is a list of dicts, each with keys:
        table, record_id, action, [old], [new], [ip], [device_info], [notes]
    All entries share the same `actor`.
    Each entry is chained to the previous via `previous_hash`.
    """
    actor_id = None
    actor_name = ""
    actor_type = ""
    if actor is not None:
        actor_id = getattr(actor, "user_id_PK", None)
        actor_name = getattr(actor, "full_name", "") or str(actor)
        actor_type = getattr(actor, "role", "") or ""

    latest = GlobalAuditTrail.objects.order_by("-trail_id").first()
    prev_hash = latest.entry_hash if (latest and latest.entry_hash) else "0" * 64

    now = timezone.now()
    instances = []
    for e in entries:
        old_serialized = _serialize_for_audit(e.get("old"))
        new_serialized = _serialize_for_audit(e.get("new"))
        old_str = json.dumps(old_serialized, sort_keys=True) if old_serialized else ""
        new_str = json.dumps(new_serialized, sort_keys=True) if new_serialized else ""
        timestamp_str = now.isoformat()

        entry_hash, hmac_sig = _compute_entry_hash(
            prev_hash, e["table"], e["record_id"], e["action"],
            old_str, new_str, timestamp_str,
        )

        instances.append(GlobalAuditTrail(
            table_name=e["table"],
            record_id=int(e["record_id"]),
            action=e["action"],
            old_values=old_serialized,
            new_values=new_serialized,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            ip_address=e.get("ip"),
            device_info=e.get("device_info"),
            notes=e.get("notes", "").strip() if isinstance(e.get("notes"), str) else e.get("notes"),
            previous_hash=prev_hash,
            entry_hash=entry_hash,
            hmac_signature=hmac_sig,
        ))
        prev_hash = entry_hash

    GlobalAuditTrail.objects.bulk_create(instances)



def _log_sensitive_read(request, table_name, record_ids, description="", device_info=None):
    """Log read access to sensitive records.
    - SensitiveReadLog: one entry per record_id
    - GlobalAuditTrail: one summary entry with notes describing the bulk read.
    """
    officer = resolve_officer_from_session(request)
    actor_id = getattr(officer, "user_id_PK", None) if officer else None
    actor_name = getattr(officer, "full_name", "") if officer else ""
    actor_type = getattr(officer, "role", "") if officer else ""
    ip = request.META.get("REMOTE_ADDR")
    if device_info is None:
        device_info = request.META.get("HTTP_USER_AGENT", "")

    batch = [
        SensitiveReadLog(
            table_name=table_name,
            record_id=rid,
            reader_type=actor_type,
            reader_id=actor_id,
            reader_name=actor_name,
            ip_address=ip,
            device_info=device_info,
            description=description,
        )
        for rid in record_ids
    ]
    SensitiveReadLog.objects.bulk_create(batch)

    _record_audit_trail(
        table=table_name,
        record_id=0,
        action="READ",
        actor=officer,
        ip=ip,
        device_info=device_info,
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


def _officer_to_json(officer):
    department = getattr(officer, "department_id_FK", None)
    return {
        "id": officer.user_id_PK,
        "full_name": officer.full_name,
        "username": officer.username,
        "email": getattr(officer, "email", "") or "",
        "role": officer.role,
        "account_status": officer.account_status,
        "term_start": officer.term_start.isoformat() if officer.term_start else "",
        "term_end": officer.term_end.isoformat() if officer.term_end else "",
        "department_id": department.department_id_PK if department else None,
        "department_name": department.name if department else "",
        "department_code": department.code if department else "",
        "created_at": officer.created_at.isoformat() if officer.created_at else "",
        "updated_at": officer.updated_at.isoformat() if officer.updated_at else "",
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
    elif table_name == "payroll_batch":
        amount = float(getattr(record, "total_amount", 0) or 0)
    elif table_name == "contribution":
        amount = float(getattr(record, "paid_amount", 0) or 0)
        verified_at = getattr(record, "payment_date", None)

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
        logger.exception("Failed to broadcast to group %s", group_name)


def _broadcast_pending_counts(target_groups: Optional[list[str]] = None) -> None:
    from core_system.models import TransactionVerification

    cache.delete_many(["auditor_pending_count", "president_pending_count"])

    auditor_pending = TransactionVerification.objects.filter(
        verification_status=Status.PENDING,
        auditor_id_FK__isnull=True,
    ).count()
    cache.set("auditor_pending_count", auditor_pending, 30)

    president_pending = TransactionVerification.objects.filter(
        verification_status=Status.AUDITOR_VERIFIED,
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
        logger.exception("Failed to send push notifications")


def _send_push_notifications(auditor_pending: int, president_pending: int) -> None:
    from core_system.models import PushSubscription, OfficerUser
    from pywebpush import webpush

    vapid_private_key = settings.VAPID_PRIVATE_KEY
    vapid_public_key = settings.VAPID_PUBLIC_KEY
    vapid_aud = VAPID_ORIGIN

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
                        "sub": VAPID_CONTACT,
                        "aud": vapid_aud,
                    },
                )
            except Exception as exc:
                logger.warning("Push notification failed for auditor subscription %s: %s", sub.pk, exc)

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
                        "sub": VAPID_CONTACT,
                        "aud": vapid_aud,
                    },
                )
            except Exception as exc:
                logger.warning("Push notification failed for president subscription %s: %s", sub.pk, exc)


def _notify_release(post, officer, request=None):
    from core_system.models import PushSubscription, OfficerUser
    from core_system.services.email_service import send_html_email
    from pywebpush import webpush

    archive = getattr(post, "archive_id_FK", None)
    member_name = archive.member_name if archive else "Unknown"
    aid_label = "Medical Aid" if post.aid_type == "medical_aid" else "Death Aid"

    total = Contribution.objects.filter(aid_tracking_post_id_FK=post).count()
    paid = Contribution.objects.filter(
        aid_tracking_post_id_FK=post, status__in=["PAID", "RECORDED"],
    ).count()
    skipped = Contribution.objects.filter(
        aid_tracking_post_id_FK=post, status="SKIPPED",
    ).count()
    ip = request.META.get("REMOTE_ADDR") if request else None

    summary = (
        f"Release completed \u2014 {aid_label} for {member_name}. "
        f"\u20b1{post.total_collected} collected | {paid}/{total} members paid"
    )

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="RELEASE_NOTIFIED",
        actor=officer,
        new={
            "total_collected": float(post.total_collected),
            "total_members": total,
            "paid_count": paid,
            "skipped_count": skipped,
        },
        ip=ip,
        notes=f"Release completed \u2014 {aid_label} for {member_name}. \u20b1{post.total_collected} from {paid}/{total} members. Released by {officer.full_name}",
    )

    _broadcast_to_group("auditor_dashboard", {
        "type": "release_notification",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "aid_label": aid_label,
        "total_collected": float(post.total_collected),
        "paid_count": paid,
        "total_count": total,
        "released_by": officer.full_name,
    })
    _broadcast_to_group("president_dashboard", {
        "type": "release_notification",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "aid_label": aid_label,
        "total_collected": float(post.total_collected),
        "paid_count": paid,
        "total_count": total,
        "released_by": officer.full_name,
    })

    try:
        for role_name in ("Auditor", "President"):
            officer_ids = OfficerUser.objects.filter(role=role_name).values_list("user_id_PK", flat=True)
            subs = PushSubscription.objects.filter(officer_id_FK__in=list(officer_ids))
            if not subs:
                continue
            payload = json.dumps({
                "title": f"Release: {member_name[:20]}\u2019s {aid_label.split()[0]} Aid",
                "body": f"\u20b1{post.total_collected} from {paid}/{total} members",
                "url": f"/{role_name.lower()}/",
            })
            for sub in subs:
                try:
                    webpush(
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                        },
                        data=payload,
                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                        vapid_claims={
                            "sub": VAPID_CONTACT,
                            "aud": VAPID_ORIGIN,
                        },
                    )
                except Exception:
                    logger.exception("Failed to send push notification for release")
    except Exception:
        logger.exception("Failed to send release push notifications")

    try:
        for role_name in ("Auditor", "President"):
            officers = OfficerUser.objects.filter(role=role_name)
            recipient_emails = [o.email for o in officers if o.email]
            if not recipient_emails:
                continue
            threading.Thread(
                target=send_html_email,
                args=(f"Release Completed \u2014 {aid_label} for {member_name}", recipient_emails, "emails/release_notification.html"),
                kwargs={
                    "context": {
                        "aid_type": aid_label,
                        "member_name": member_name,
                        "total_collected": f"{post.total_collected:,.2f}",
                        "paid_count": paid,
                        "total_count": total,
                        "skipped_count": skipped,
                        "released_by": officer.full_name,
                        "released_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
                    },
                },
                daemon=True,
            ).start()
    except Exception:
        logger.exception("Failed to send release email notifications")


ENTITY_LABELS = {
    "membership_fee": "Membership Fee",
    "monthly_dues": "Monthly Dues",
    "medical_aid": "Medical Aid",
    "death_aid": "Death Aid",
}


def _get_month_covered(record, table_name):
    if table_name == "membership_fee":
        d = getattr(record, "payment_date", None)
        return d.isoformat() if d else ""
    if table_name == "monthly_dues":
        return getattr(record, "month_covered", "") or ""
    if table_name == "medical_aid":
        d = getattr(record, "request_date", None)
        return d.isoformat() if d else ""
    if table_name == "death_aid":
        d = getattr(record, "claim_date", None)
        return d.isoformat() if d else ""
    return ""


def _get_amount_value(record, table_name):
    if table_name == "membership_fee":
        return str(getattr(record, "amount", 0) or 0)
    if table_name == "monthly_dues":
        return str(getattr(record, "amount", 0) or 0)
    if table_name == "medical_aid":
        return str(getattr(record, "requested_amount", 0) or 0)
    if table_name == "death_aid":
        return str(getattr(record, "benefit_amount", 0) or 0)
    return ""


def _serialize_editable_fields(record, table_name):
    field_names = UPDATABLE_FIELDS.get(table_name, [])
    fields = []
    for fname in field_names:
        val = getattr(record, fname, None)
        ftype = "text"
        if val is not None and hasattr(val, "isoformat"):
            val = val.isoformat()
            ftype = "date"
        elif val is not None and hasattr(val, "__float__"):
            val = str(val)
            ftype = "number"
        if fname in ("payment_method", "payment_status", "document_status", "claim_type", "relationship_group", "payment_status", "method"):
            ftype = "select"
        fields.append({
            "name": fname,
            "label": fname.replace("_", " ").title(),
            "value": str(val) if val is not None else "",
            "type": ftype,
            "required": True,
        })
    return fields


def _get_proof_url_for_record(record, table_name):
    Model = MODEL_MAP.get(table_name)
    if Model:
        return _get_proof_url(Model, record.pk)
    return ""


@require_GET
@never_cache
def shared_returns_list(request):
    from core_system.guards import require_role
    guard = require_role(request, role=["Treasurer", "Auditor"])
    if guard:
        return guard

    officer = resolve_officer_from_session(request)
    role = (officer.role or "").lower() if officer else ""

    tvs = TransactionVerification.objects.filter(
        verification_status=Status.RETURNED_REVISION,
    ).select_related("returned_by_auditor_id_FK")

    if role == "auditor" and officer:
        tvs = tvs.filter(returned_by_auditor_id_FK=officer)

    results = []
    for tv in tvs:
        Model = MODEL_MAP.get(tv.table_name)
        if not Model or tv.table_name == "payroll_batch" or tv.table_name == "contribution":
            continue
        try:
            record = Model.objects.select_related("member_id_FK").get(pk=tv.record_id)
        except Model.DoesNotExist:
            continue

        revision = GlobalAuditTrail.objects.filter(
            table_name=tv.table_name,
            record_id=tv.record_id,
            action__in=["RETURNED", "CORRECTION_REQUIRED"],
        ).order_by("-timestamp").first()

        member = getattr(record, "member_id_FK", None)
        results.append({
            "tv_id": tv.verification_id,
            "table_name": tv.table_name,
            "record_id": tv.record_id,
            "entity_label": ENTITY_LABELS.get(tv.table_name, tv.table_name.replace("_", " ").title()),
            "member_name": member.full_name if member else "",
            "member_id": member.member_id_PK if member else None,
            "month_covered": _get_month_covered(record, tv.table_name),
            "amount": _get_amount_value(record, tv.table_name),
            "return_count": tv.return_count,
            "returned_by": tv.returned_by_auditor_id_FK.full_name if tv.returned_by_auditor_id_FK else "",
            "returned_at": revision.timestamp.isoformat() if revision and revision.timestamp else "",
            "returned_reason": tv.returned_reason or "",
            "auditor_remarks": tv.auditor_remarks or "",
            "resubmitted": False,
            "fields": _serialize_editable_fields(record, tv.table_name),
            "proof_url": _get_proof_url_for_record(record, tv.table_name),
        })

    return JsonResponse({"ok": True, "returns": results, "role": role})
