import hashlib
from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from core_system.auth_utils import (
    create_access_session,
    log_login_attempt,
    verify_officer_password,
)
from core_system.models import AccessSession, LoginAttemptLog, OfficerUser


def _workspace_redirect(role: str) -> str:
    role_norm = (role or "").strip().lower()
    if role_norm == "treasurer":
        return "/treasurer/"
    if role_norm == "auditor":
        return "/auditor/"
    if role_norm == "president":
        return "/president/"
    return "/"


@csrf_protect
def officer_login(request: HttpRequest) -> HttpResponse:
    """Role-based login using OfficerUser (SHA-256 hex stored in password_hash)."""

    if request.method == "GET":
        # login.html is already wired as template; we render it directly.
        return render(request, "website/login.html")

    username = (request.POST.get("username") or "").strip()
    password_input = request.POST.get("password") or ""

    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT")

    try:
        officer = OfficerUser.objects.get(username=username)
    except OfficerUser.DoesNotExist:
        officer = None

    if officer is not None:
        ok = verify_officer_password(officer=officer, password_input=password_input)
        if ok and (officer.account_status or "").lower() == "active":
            session, token = create_access_session(
                officer=officer,
                ip_address=ip_address,
                device_info=user_agent,
            )
            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="Success",
                user_id=officer.user_id_PK,
            )
            request.session["access_token"] = token
            request.session["officer_id"] = officer.user_id_PK
            request.session["role"] = officer.role
            return redirect(_workspace_redirect(officer.role))

        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Invalid credentials",
            user_id=getattr(officer, "user_id_PK", None),
        )
    else:
        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Invalid credentials",
            user_id=None,
        )

    # Login failed -> show same template with form errors-ish behavior.
    return render(request, "website/login.html", context={"form": {"errors": [True]}})
