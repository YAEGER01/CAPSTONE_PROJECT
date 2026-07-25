import json
import logging
from typing import Any, Dict

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core_system.auth_utils import sha256_hex
from core_system.guards import require_role
from core_system.models import (
    AccessSession,
    Department,
    GlobalAuditTrail,
    LoginAttemptLog,
    OfficerUser,
    OutgoingEmail,
    SystemSetting,
    BackupJob,
)
from core_system.shared_view_utils import (
    _officer_to_json,
    _record_audit_trail,
    resolve_officer_from_session,
)

logger = logging.getLogger(__name__)


def _resolve_admin(request: HttpRequest):
    stored_id = request.session.get("officer_id")
    if stored_id is None:
        return None
    try:
        return OfficerUser.objects.get(user_id_PK=int(stored_id))
    except Exception:
        return None


def _extract_request_data(request: HttpRequest) -> Dict[str, Any]:
    if request.content_type and "json" in request.content_type.lower():
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    if request.body:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return request.POST.dict()


def _parse_iso_date(value: Any):
    raw = (value or "").strip() if isinstance(value, str) else value
    if not raw:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(raw)).date()
    except (TypeError, ValueError):
        return None


@never_cache
def admin_dashboard(request):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    officer_full_name = ""
    stored_id = request.session.get("officer_id")
    if stored_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(stored_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
        except Exception:
            pass
    context = {
        "officer_full_name": officer_full_name,
        "officer_role": "Admin",
        "access_token": request.session.get("access_token", ""),
        "departments": Department.objects.filter(is_active=True).order_by("name"),
    }
    if not officer_full_name.strip():
        context["officer_full_name"] = "Admin"
    return render(request, "website/Admin/admin_dashboard.html", context)


@require_GET
def admin_officers_list(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    officers = OfficerUser.objects.select_related("department_id_FK").order_by("-created_at", "full_name")
    return JsonResponse({"ok": True, "officers": [_officer_to_json(o) for o in officers]})


@require_POST
@transaction.atomic
def admin_officers_create(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    payload = _extract_request_data(request)
    username = (payload.get("username") or "").strip()
    full_name = (payload.get("full_name") or "").strip()
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "").strip()
    email = (payload.get("email") or "").strip() or None
    account_status = (payload.get("account_status") or "Active").strip()
    term_start = _parse_iso_date(payload.get("term_start"))
    term_end = _parse_iso_date(payload.get("term_end"))
    department_id = payload.get("department_id") or payload.get("department")

    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)
    if not password:
        return JsonResponse({"ok": False, "error": "Password is required."}, status=400)
    try:
        validate_password(password)
    except DjangoValidationError as e:
        return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=400)
    if OfficerUser.objects.filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)

    department = None
    if department_id not in (None, "", 0, "0"):
        department = Department.objects.filter(department_id_PK=int(department_id)).first()
        if department is None:
            return JsonResponse({"ok": False, "error": "Department not found."}, status=400)

    officer = OfficerUser.objects.create(
        full_name=full_name,
        username=username,
        password_hash=sha256_hex(password),
        role=role,
        email=email,
        department_id_FK=department,
        account_status=account_status,
        term_start=term_start,
        term_end=term_end,
    )

    admin = _resolve_admin(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="CREATED",
        actor=admin,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Admin created officer account for {officer.full_name}",
    )
    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def admin_officers_update(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    officer = get_object_or_404(OfficerUser.objects.select_related("department_id_FK"), pk=officer_id)
    payload = _extract_request_data(request)

    username = (payload.get("username") or officer.username).strip()
    full_name = (payload.get("full_name") or officer.full_name).strip()
    role = (payload.get("role") or officer.role).strip()
    email = (payload.get("email") or getattr(officer, "email", "") or "").strip() or None
    account_status = (payload.get("account_status") or officer.account_status).strip()
    term_start = _parse_iso_date(payload.get("term_start")) if payload.get("term_start") not in (None, "") else officer.term_start
    term_end = _parse_iso_date(payload.get("term_end")) if payload.get("term_end") not in (None, "") else officer.term_end
    password = (payload.get("password") or "").strip()
    department_id = payload.get("department_id") or payload.get("department")

    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)
    if OfficerUser.objects.exclude(pk=officer.pk).filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)

    department = officer.department_id_FK
    if department_id not in (None, "", 0, "0"):
        department = Department.objects.filter(department_id_PK=int(department_id)).first()
        if department is None:
            return JsonResponse({"ok": False, "error": "Department not found."}, status=400)
    elif department_id in ("", None):
        department = None if payload.get("clear_department") else department

    officer.full_name = full_name
    officer.username = username
    officer.role = role
    officer.email = email
    officer.account_status = account_status
    officer.term_start = term_start
    officer.term_end = term_end
    officer.department_id_FK = department
    if password:
        try:
            validate_password(password)
        except DjangoValidationError as e:
            return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=400)
        officer.password_hash = sha256_hex(password)

    update_fields = [
        "full_name", "username", "role", "email", "account_status",
        "term_start", "term_end", "department_id_FK", "updated_at",
    ]
    if password:
        update_fields.append("password_hash")
    officer.save(update_fields=update_fields)

    admin = _resolve_admin(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="UPDATED",
        actor=admin,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Admin updated officer account for {officer.full_name}",
    )
    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def admin_officers_reset_password(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    officer = get_object_or_404(OfficerUser, pk=officer_id)
    import secrets
    temp_password = secrets.token_urlsafe(10)
    try:
        validate_password(temp_password)
    except DjangoValidationError as e:
        return JsonResponse({"ok": False, "error": "; ".join(e.messages)}, status=400)
    officer.password_hash = sha256_hex(temp_password)
    officer.save(update_fields=["password_hash", "updated_at"])

    admin = _resolve_admin(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="PASSWORD_RESET",
        actor=admin,
        new={"username": officer.username, "temp_password_generated": True},
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Admin reset password for {officer.full_name} — temp password: {temp_password}",
    )
    return JsonResponse({"ok": True, "message": "Password reset. Temporary password recorded in audit trail."})


@require_POST
@transaction.atomic
def admin_officers_toggle_status(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    officer = get_object_or_404(OfficerUser, pk=officer_id)
    new_status = "Inactive" if officer.account_status == "Active" else "Active"
    officer.account_status = new_status
    officer.save(update_fields=["account_status", "updated_at"])

    admin = _resolve_admin(request)
    action = "ACTIVATED" if new_status == "Active" else "DEACTIVATED"
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action=action,
        actor=admin,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Admin {action.lower()} account for {officer.full_name}",
    )
    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


# ==========================================================================
# PLACEHOLDER ENDPOINTS
# ==========================================================================

@require_GET
def admin_audit_trail(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    entries = GlobalAuditTrail.objects.select_related().order_by("-timestamp")
    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))
    total = entries.count()
    rows = [
        {
            "trail_id": e.trail_id,
            "table_name": e.table_name,
            "record_id": e.record_id,
            "action": e.action,
            "actor_name": e.actor_name,
            "old_values": e.old_values,
            "new_values": e.new_values,
            "notes": e.notes,
            "ip_address": str(e.ip_address) if e.ip_address else None,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in entries[offset:offset + limit]
    ]
    return JsonResponse({"ok": True, "total": total, "entries": rows})


@require_GET
def admin_login_attempts(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    attempts = LoginAttemptLog.objects.order_by("-attempted_at")
    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))
    total = attempts.count()
    rows = [
        {
            "id": a.attempt_id_PK,
            "username": a.username_used,
            "result": a.result,
            "ip": str(a.ip_address) if a.ip_address else None,
            "timestamp": a.attempted_at.isoformat() if a.attempted_at else None,
        }
        for a in attempts[offset:offset + limit]
    ]
    return JsonResponse({"ok": True, "total": total, "attempts": rows})


@require_GET
def admin_sessions(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    sessions = AccessSession.objects.select_related("user_id_FK").order_by("-issued_at")
    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))
    total = sessions.count()
    rows = [
        {
            "id": s.session_id_PK,
            "officer_name": getattr(s.user_id_FK, "full_name", ""),
            "officer_username": getattr(s.user_id_FK, "username", ""),
            "ip": s.ip_address,
            "status": s.session_status,
            "trusted": s.trusted_device,
            "created": s.issued_at.isoformat() if s.issued_at else None,
            "expires": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in sessions[offset:offset + limit]
    ]
    return JsonResponse({"ok": True, "total": total, "sessions": rows})


@require_GET
def admin_email_queue(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    emails = OutgoingEmail.objects.order_by("-created_at")
    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))
    total = emails.count()
    rows = [
        {
            "id": e.outgoing_email_id,
            "recipient": e.recipient,
            "subject": e.subject,
            "status": e.status,
            "created": e.created_at.isoformat() if e.created_at else None,
        }
        for e in emails[offset:offset + limit]
    ]
    return JsonResponse({"ok": True, "total": total, "emails": rows})


@require_GET
def admin_settings(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    settings_list = SystemSetting.objects.all().order_by("setting_key")
    data = {s.setting_key: s.setting_value for s in settings_list}
    return JsonResponse({"ok": True, "settings": data})


@require_GET
def admin_backups(request: HttpRequest):
    guard = require_role(request, role="Admin")
    if guard is not None:
        return guard
    jobs = BackupJob.objects.order_by("-started_at")
    rows = [
        {
            "job_id": j.job_id,
            "backup_type": j.backup_type,
            "backup_status": j.backup_status,
            "created_at": j.started_at.isoformat() if j.started_at else None,
        }
        for j in jobs
    ]
    return JsonResponse({"ok": True, "jobs": rows})