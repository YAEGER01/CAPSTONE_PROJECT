import logging
import secrets
import time
import threading
from datetime import timedelta

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core_system.auth_utils import (
    create_access_session,
    log_login_attempt,
    verify_officer_password,
)
from core_system.models import AccessSession, OfficerUser
from core_system.services.mfa_service import (
    generate_mfa_secret,
    generate_otp,
    send_mfa_email,
    verify_otp,
    MFA_EMAIL_RATE_LIMIT_SECONDS,
)

MFA_SESSION_KEY = "mfa_pre_auth_token"
MFA_OFFICER_ID_KEY = "mfa_officer_id"
MFA_USERNAME_KEY = "mfa_username"


def _queue_mfa_email(officer, otp):
    from core_system.services.email_service import queue_email, process_email_queue
    queue_email(
        subject="CAUFA MFA Verification Code",
        recipient_list=[officer.email],
        html_template="emails/mfa_challenge.html",
        context={
            "full_name": officer.full_name,
            "otp_code": otp,
            "expiry_minutes": 5,
        },
    )
    threading.Thread(target=process_email_queue, kwargs={"batch_size": 5}, daemon=True).start()


def _check_term_validity(officer: OfficerUser) -> tuple[bool, str]:
    term_start = getattr(officer, "term_start", None)
    term_end = getattr(officer, "term_end", None)
    if not term_start or not term_end:
        return True, ""
    today = timezone.localdate()
    if today < term_start:
        return False, f"Your officer term has not started yet. Term begins on {term_start.isoformat()}."
    if today > term_end:
        return False, f"Your officer term expired on {term_end.isoformat()}. Please contact the board."
    return True, ""


def _term_info(officer: OfficerUser) -> dict:
    term_start = getattr(officer, "term_start", None)
    term_end = getattr(officer, "term_end", None)
    today = timezone.localdate()
    is_expired = False
    days_until_expiry = None
    if term_start and term_end:
        if today > term_end:
            is_expired = True
        else:
            days_until_expiry = (term_end - today).days
    return {
        "term_start": term_start.isoformat() if term_start else "",
        "term_end": term_end.isoformat() if term_end else "",
        "is_expired": is_expired,
        "days_until_expiry": days_until_expiry,
    }


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
        if "access_token" in request.session:
            return redirect(_workspace_redirect(request.session.get("role", "")))

        # If the MFA keys were set by the POST handler (redirect from login POST),
        # preserve them and clear the flag. Otherwise clear stale MFA state.
        if request.session.pop("_mfa_initiated", None):
            pass  # MFA keys are fresh from POST — keep them
        else:
            for key in (MFA_SESSION_KEY, MFA_OFFICER_ID_KEY, MFA_USERNAME_KEY, "mfa_email_warning"):
                request.session.pop(key, None)

        context = {}
        if request.session.get(MFA_SESSION_KEY):
            context["form"] = {
                "errors": [],
                "mfa_required": True,
                "pre_auth_token": request.session.get(MFA_SESSION_KEY, ""),
                "username": request.session.get(MFA_USERNAME_KEY, ""),
                "delivery": "Email",
            }
            if request.session.get("mfa_email_warning"):
                context["form"]["email_warning"] = request.session.get("mfa_email_warning")
                del request.session["mfa_email_warning"]
        return render(request, "website/login.html", context)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    username = (request.POST.get("username") or "").strip()
    password_input = request.POST.get("password") or ""
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT") or "Unknown"

    try:
        officer = OfficerUser.objects.get(username=username)
    except OfficerUser.DoesNotExist:
        officer = None

    password_ok = False
    if officer is not None:
        password_ok = verify_officer_password(officer=officer, password_input=password_input)

    if officer and password_ok and (officer.account_status or "").lower() == "active":
        term_ok, term_error = _check_term_validity(officer)
        if not term_ok:
            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="Term expired",
                user_id=officer.user_id_PK,
            )
            if is_ajax:
                return JsonResponse({"ok": False, "error": term_error, "term_expired": True}, status=400)
            messages.error(request, term_error, extra_tags="term_expired")
            return redirect("login")

        if officer.mfa_enabled and officer.mfa_secret:
            now = timezone.now()
            time_limit = now - timedelta(seconds=MFA_EMAIL_RATE_LIMIT_SECONDS)
            rate_limited = False

            if not officer.last_mfa_email_sent_at or officer.last_mfa_email_sent_at < time_limit:
                otp = generate_otp(officer.mfa_secret)
                _queue_mfa_email(officer, otp)
                email_sent = True
                officer.last_mfa_email_sent_at = now
                officer.save(update_fields=["last_mfa_email_sent_at"])
            else:
                email_sent = False
                rate_limited = True

            pre_auth_token = secrets.token_urlsafe(32)
            request.session[MFA_SESSION_KEY] = pre_auth_token
            request.session[MFA_OFFICER_ID_KEY] = officer.user_id_PK
            request.session[MFA_USERNAME_KEY] = officer.username
            request.session.set_expiry(600)

            if rate_limited:
                request.session["mfa_email_warning"] = "A verification code was already sent recently. Please check your inbox."
            elif not email_sent:
                request.session["mfa_email_warning"] = "Failed to send verification email. Please use the resend option or contact support."

            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="MFA_REQUIRED",
                user_id=officer.user_id_PK,
            )
            request.session["_mfa_initiated"] = True
            if is_ajax:
                return JsonResponse({"ok": True, "mfa_required": True, "redirect_url": "/login/"})
            return redirect("login")

        session, token = create_access_session(officer=officer, ip_address=ip_address, device_info=user_agent)
        request.session["access_token"] = token
        request.session["officer_id"] = officer.user_id_PK
        request.session["role"] = officer.role
        
        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Success",
            user_id=officer.user_id_PK,
        )
        if is_ajax:
            return JsonResponse({"ok": True, "redirect_url": _workspace_redirect(officer.role)})
        return redirect(_workspace_redirect(officer.role))

    log_login_attempt(
        username=username,
        ip_address=ip_address,
        device_info=user_agent,
        result="Invalid credentials",
        user_id=officer.user_id_PK if officer else None,
    )
    if is_ajax:
        return JsonResponse({"ok": False, "error": "Invalid username or password."}, status=401)
    messages.error(request, "Invalid username or password.")
    return redirect("login")


@require_POST
@csrf_protect
def mfa_verify(request: HttpRequest) -> JsonResponse:
    """Verifies incoming OTP code for step-up login flow."""
    otp = (request.POST.get("otp") or "").strip()
    pre_auth_token = (request.POST.get("pre_auth_token") or "").strip() or request.session.get(MFA_SESSION_KEY)

    if not pre_auth_token or not otp:
        return JsonResponse({"ok": False, "error": "Missing code or token context."}, status=400)

    # Validate session pre-auth token
    session_token = request.session.get(MFA_SESSION_KEY)
    if not session_token or session_token != pre_auth_token:
        return JsonResponse({"ok": False, "error": "Invalid or expired session. Please log in again."}, status=400)

    officer_id = request.session.get(MFA_OFFICER_ID_KEY)
    if not officer_id:
        return JsonResponse({"ok": False, "error": "Pre-auth context expired."}, status=400)

    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer account not found."}, status=404)

    # Verify the code
    import logging as _lg
    _log = _lg.getLogger(__name__)
    _log.info("mfa_verify: officer=%s otp_input=%s", officer.full_name, otp)
    if not verify_otp(officer.mfa_secret, otp):
        _log.warning("mfa_verify FAILED: secret=%s...", officer.mfa_secret[:8])
        return JsonResponse({"ok": False, "error": "Invalid verification code."}, status=401)

    term_ok, term_error = _check_term_validity(officer)
    if not term_ok:
        request.session.pop(MFA_SESSION_KEY, None)
        request.session.pop(MFA_OFFICER_ID_KEY, None)
        request.session.pop(MFA_USERNAME_KEY, None)
        log_login_attempt(
            username=officer.username,
            ip_address=request.META.get("REMOTE_ADDR") or "0.0.0.0",
            device_info=request.META.get("HTTP_USER_AGENT"),
            result="Term expired",
            user_id=officer.user_id_PK,
        )
        return JsonResponse({"ok": False, "error": term_error, "term_expired": True}, status=403)

    # Success: Clean up temporary keys
    request.session.pop(MFA_SESSION_KEY, None)
    request.session.pop(MFA_OFFICER_ID_KEY, None)
    request.session.pop(MFA_USERNAME_KEY, None)

    # Establish full session
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT")
    session, token = create_access_session(
        officer=officer,
        ip_address=ip_address,
        device_info=user_agent,
    )
    
    request.session["access_token"] = token
    request.session["officer_id"] = officer.user_id_PK
    request.session["role"] = officer.role
    request.session.set_expiry(None)

    log_login_attempt(
        username=officer.username,
        ip_address=ip_address,
        device_info=user_agent,
        result="Success",
        user_id=officer.user_id_PK,
    )

    return JsonResponse({
        "ok": True,
        "redirect_url": _workspace_redirect(officer.role),
    })


@require_POST
@csrf_protect
def mfa_challenge(request: HttpRequest) -> JsonResponse:
    """Triggered when user requests to resend OTP via AJAX during login."""
    username = (request.POST.get("username") or "").strip()
    session_username = request.session.get(MFA_USERNAME_KEY)

    if not username or username != session_username:
        return JsonResponse({"ok": False, "error": "Session mismatch. Re-authenticate from login screen."}, status=400)

    officer_id = request.session.get(MFA_OFFICER_ID_KEY)
    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer context missing."}, status=404)

    now = timezone.now()
    time_limit = now - timedelta(seconds=MFA_EMAIL_RATE_LIMIT_SECONDS)

    if not officer.last_mfa_email_sent_at or officer.last_mfa_email_sent_at < time_limit:
        otp = generate_otp(officer.mfa_secret)
        email_sent = send_mfa_email(officer, otp)
        if email_sent:
            officer.last_mfa_email_sent_at = now
            officer.save(update_fields=["last_mfa_email_sent_at"])
            request.session.set_expiry(600)
        return JsonResponse({
            "ok": email_sent,
            "message": "Verification code sent via email." if email_sent else "Failed to send email. Try again.",
            "delivery": "email",
        })

    wait_minutes = int(MFA_EMAIL_RATE_LIMIT_SECONDS / 60 - (now - officer.last_mfa_email_sent_at).total_seconds() / 60)
    return JsonResponse({
        "ok": False,
        "error": f"Email OTP was recently sent. Please wait {wait_minutes} minutes.",
        "rate_limited": True,
    }, status=429)


@require_POST
@csrf_protect
def mfa_enable(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    if not officer.mfa_enabled:
        officer.mfa_enabled = True
        officer.mfa_secret = generate_mfa_secret()
        officer.save(update_fields=["mfa_enabled", "mfa_secret"])

    return JsonResponse({
        "ok": True,
        "message": "MFA enabled. You will be asked for a code at login.",
    })


@require_POST
@csrf_protect
def mfa_disable(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    officer.mfa_enabled = False
    officer.mfa_secret = None
    officer.save(update_fields=["mfa_enabled", "mfa_secret"])

    return JsonResponse({"ok": True, "message": "MFA disabled."})


@csrf_protect
def mfa_challenge_page(request: HttpRequest) -> HttpResponse:
    return render(request, "website/mfa_challenge.html")


@require_POST
@csrf_protect
def zero_trust_challenge(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    if not officer.mfa_enabled or not officer.mfa_secret:
        return JsonResponse({"ok": False, "error": "MFA must be enabled to perform zero trust verification."}, status=400)

    otp = generate_otp(officer.mfa_secret)
    import logging as _lg
    _lg.getLogger(__name__).info(
        "ZT challenge: officer=%s otp=%s now=%s",
        officer.full_name, otp, __import__("time").time(),
    )
    request.session["zero_trust_otp"] = {
        "otp": otp,
        "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat(),
    }

    email_sent = send_mfa_email(officer=officer, otp=otp)
    return JsonResponse({
        "ok": email_sent,
        "message": "Verification code sent via email." if email_sent else "Failed to send email. Try again.",
        "delivery": "email",
        "sent": email_sent,
    })


@require_GET
def zero_trust_status(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "verified": False, "error": "Not authenticated."}, status=401)
    from core_system.guards import check_zero_trust
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return JsonResponse({"ok": True, "verified": False})
    return JsonResponse({"ok": True, "verified": True})


@require_POST
@csrf_protect
def zero_trust_verify(request: HttpRequest) -> HttpResponse:
    otp_input = (request.POST.get("otp") or "").strip()
    stored = request.session.get("zero_trust_otp")
    stored_officer_id = request.session.get("officer_id")
    token = request.session.get("access_token")

    if not stored or not otp_input or not stored_officer_id or not token:
        return JsonResponse({"ok": False, "error": "Invalid verification session."}, status=400)

    expires_at_str = stored.get("expires_at")
    if expires_at_str:
        expires_at = timezone.datetime.fromisoformat(expires_at_str)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)
        if timezone.now() > expires_at:
            return JsonResponse({"ok": False, "error": "Verification code expired."}, status=400)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    computed_otp = generate_otp(officer.mfa_secret)
    logger.info(
        "ZT verify: officer=%s otp_input=%s computed_otp=%s now=%s",
        officer.full_name, otp_input, computed_otp, time.time(),
    )
    if not verify_otp(officer.mfa_secret, otp_input):
        return JsonResponse({"ok": False, "error": "Invalid verification code."}, status=401)

    try:
        session = AccessSession.objects.get(token_id=token)
        session.trusted_device = True
        session.ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
        session.device_info = request.META.get("HTTP_USER_AGENT")
        session.last_verified_location = {"ip": session.ip_address}
        policy = session.session_policy or {}
        policy["zt_verified_at"] = timezone.now().isoformat()
        session.session_policy = policy
        session.save()
    except AccessSession.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Access session not found."}, status=404)

    request.session.pop("zero_trust_otp", None)

    return JsonResponse({"ok": True, "message": "Zero Trust verification successful."})


@require_GET
def term_info(request: HttpRequest):
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    return JsonResponse({"ok": True, **_term_info(officer)})