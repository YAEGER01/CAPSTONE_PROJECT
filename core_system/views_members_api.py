from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core_system.api_utils import member_to_json
from core_system.guards import require_role
from core_system.models import (
    Member,
    MembershipFee,
    MonthlyDues,
    MedicalAid,
    DeathAid,
    TransactionVerification,
    RevisionLog,
)
from django.contrib.contenttypes.models import ContentType


@require_GET
def treasurer_members_list(request):
    """Return all members for Treasurer dashboard."""
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
    """Return count of active members for Treasurer KPI."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    active_count = Member.objects.filter(membership_status="Active").count()

    return JsonResponse({"ok": True, "active_count": active_count})


MODEL_MAP = {
    "membership_fee": MembershipFee,
    "monthly_dues": MonthlyDues,
    "medical_aid": MedicalAid,
    "death_aid": DeathAid,
}


def _payment_item_to_json(kind: str, obj) -> dict:
    """Serialize payment records for treasurer dashboard."""
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
def treasurer_records_requiring_revision(request):
    """Return records flagged as 'Returned for Revision' for Treasurer dashboard."""
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

        revision_log = RevisionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Model),
            object_id=tv.record_id
        ).order_by("-created_at").first()

        if table_name in ("membership_fee", "monthly_dues"):
            item = _payment_item_to_json(table_name.replace("_", ""), record)
            item["verificationStatus"] = tv.verification_status
            item["rejection_reason"] = revision_log.rejection_reason if revision_log else ""
            items.append(item)

    return JsonResponse({"ok": True, "records": items})

