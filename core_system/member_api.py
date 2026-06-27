from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core_system.guards import require_role
from core_system.models import Member


@require_POST
def treasurer_member_update(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    payload_member_id = (request.POST.get("member_id") or "").strip()
    if not payload_member_id:
        return JsonResponse({"ok": False, "error": "member_id is required."}, status=400)

    member_id_clean = payload_member_id
    if member_id_clean.upper().startswith("M-"):
        member_id_clean = member_id_clean[2:]

    try:
        member_pk = int(member_id_clean)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid member_id."}, status=400)

    try:
        member = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    # Update only provided fields
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

    # member model requires employment_status + membership_status to be non-null.
    if "employment_status" in fields and fields["employment_status"] is None:
        return JsonResponse({"ok": False, "error": "employment_status cannot be empty."}, status=400)
    if "membership_status" in fields and fields["membership_status"] is None:
        return JsonResponse({"ok": False, "error": "membership_status cannot be empty."}, status=400)

    for k, v in fields.items():
        setattr(member, k, v)

    # If full_name empty -> reject
    if hasattr(member, "full_name") and not (member.full_name or "").strip():
        return JsonResponse({"ok": False, "error": "full_name is required."}, status=400)

    member.save()

    return JsonResponse({"ok": True, "member": {"id": member.member_id_PK, "full_name": member.full_name}})


@require_POST
def treasurer_member_retire(request):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    payload_member_id = (request.POST.get("member_id") or "").strip()
    if not payload_member_id:
        return JsonResponse({"ok": False, "error": "member_id is required."}, status=400)

    member_id_clean = payload_member_id
    if member_id_clean.upper().startswith("M-"):
        member_id_clean = member_id_clean[2:]

    try:
        member_pk = int(member_id_clean)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid member_id."}, status=400)

    try:
        member = Member.objects.get(member_id_PK=member_pk)
    except Member.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Member not found."}, status=404)

    member.membership_status = "retired"
    member.employment_status = "retired"
    member.save()

    return JsonResponse({"ok": True, "member_id": member.member_id_PK})

