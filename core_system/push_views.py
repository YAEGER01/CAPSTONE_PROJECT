from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core_system.guards import require_role
from core_system.models import OfficerUser, PushSubscription


@require_POST
@csrf_exempt
def push_subscribe(request: HttpRequest):
    guard = require_role(request, role=None)
    if guard is not None:
        return guard

    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    endpoint = body.get("endpoint", "").strip()
    keys = body.get("keys", {})
    p256dh = keys.get("p256dh", "").strip()
    auth = keys.get("auth", "").strip()
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    if not endpoint or not p256dh or not auth:
        return JsonResponse({"ok": False, "error": "Missing endpoint or keys."}, status=400)

    PushSubscription.objects.update_or_create(
        officer_id_FK=officer,
        endpoint=endpoint,
        defaults={
            "p256dh_key": p256dh,
            "auth_key": auth,
            "user_agent": user_agent,
        },
    )

    return JsonResponse({"ok": True, "message": "Subscription saved."})


@require_POST
@csrf_exempt
def push_unsubscribe(request: HttpRequest):
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    endpoint = body.get("endpoint", "").strip()
    if not endpoint:
        return JsonResponse({"ok": False, "error": "Missing endpoint."}, status=400)

    deleted, _ = PushSubscription.objects.filter(
        officer_id_FK=stored_officer_id,
        endpoint=endpoint,
    ).delete()

    return JsonResponse({"ok": True, "deleted": deleted})
