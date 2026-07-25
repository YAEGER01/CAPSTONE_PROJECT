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
    encrypt_secret,
    decrypt_secret,
    generate_mfa_secret,
    generate_otp,
    send_mfa_email,
    verify_otp,
    MFA_EMAIL_RATE_LIMIT_SECONDS,
)

def obfuscate_email(email: str | None) -> str:
    if not email or "@" not in email:
        return email or ""
    local, domain = email.split("@", 1)
    if len(local) <= 3:
        return local[0] + "***@" + domain
    visible_start = local[:2]
    visible_end = local[-1]
    middle = "*" * (len(local) - 3)
    return visible_start + middle + visible_end + "@" + domain


MFA_SESSION_KEY = "mfa_pre_auth_token"
MFA_OFFICER_ID_KEY = "mfa_officer_id"
MFA_USERNAME_KEY = "mfa_username"


def _queue_mfa_email(officer, otp, action=""):
    from core_system.services.email_service import queue_email, process_email_queue
    subject = f"CAUFA - Verify {action}" if action else "CAUFA MFA Verification Code"
    queue_email(
        subject=subject,
        recipient_list=[officer.email],
        html_template="emails/mfa_challenge.html",
        context={
            "full_name": officer.full_name,
            "otp_code": otp,
            "expiry_minutes": 5,
            "action": action,
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
    if role_norm == "admin":
        return "/supaadmin/"
    if role_norm == "treasurer":
        return "/treasurer/"
    if role_norm == "auditor":
        return "/auditor/"
    if role_norm == "president":
        return "/president/"
    return "/"


@csrf_protect
def officer_login(request: HttpRequest) -> HttpResponse:
    # TODO: Split this view into separate officer_login_get and officer_login_post functions
    """Role-based login using OfficerUser (SHA-256 hex stored in password_hash)."""
    if request.method == "GET":
        token = request.session.get("access_token")
        if token:
            try:
                sess = AccessSession.objects.get(token_id=token)
                if sess.session_status == "active" and sess.expires_at > timezone.now() and sess.revoked_at is None:
                    role = request.session.get("role", "")
                    if role:
                        return redirect(_workspace_redirect(role))
            except AccessSession.DoesNotExist:
                pass

        # If the MFA keys were set by the POST handler (redirect from login POST),
        # preserve them and clear the flag. Otherwise clear stale MFA state.
        if request.session.pop("_mfa_initiated", None):
            pass  # MFA keys are fresh from POST — keep them
        else:
            for key in (MFA_SESSION_KEY, MFA_OFFICER_ID_KEY, MFA_USERNAME_KEY, "mfa_email_warning"):
                request.session.pop(key, None)

        context = {}
        if request.session.get(MFA_SESSION_KEY):
            officer_email = ""
            officer_id = request.session.get(MFA_OFFICER_ID_KEY)
            if officer_id:
                try:
                    officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
                    officer_email = obfuscate_email(officer.email)
                except Exception:
                    pass
            context["form"] = {
                "errors": [],
                "mfa_required": True,
                "pre_auth_token": request.session.get(MFA_SESSION_KEY, ""),
                "username": request.session.get(MFA_USERNAME_KEY, ""),
                "delivery": "Email",
                "officer_email": officer_email,
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

        if not officer.email:
            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="No email bound",
                user_id=officer.user_id_PK,
            )
            if is_ajax:
                return JsonResponse({"ok": False, "error": "Valid credentials but no email is bound to this account.", "no_email": True})
            messages.error(request, "Your account has no email bound. Please contact support.")
            return redirect("login")

        if not officer.mfa_secret:
            officer.mfa_secret = encrypt_secret(generate_mfa_secret())
            officer.save(update_fields=["mfa_secret"])

        now_ts = timezone.now().timestamp()
        time_limit_ts = now_ts - MFA_EMAIL_RATE_LIMIT_SECONDS
        rate_limited = False
        last_sent_ts = request.session.get("mfa_last_sent_ts")

        if not last_sent_ts or last_sent_ts < time_limit_ts:
            otp = generate_otp(officer.mfa_secret)
            _queue_mfa_email(officer, otp)
            email_sent = True
            request.session["mfa_last_sent_ts"] = now_ts
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

    # Check for one-time-use (replay protection)
    used_otps = set(request.session.get("mfa_used_otps", []))
    if otp in used_otps:
        return JsonResponse({"ok": False, "error": "This code has already been used."}, status=401)

    # Verify the code
    import logging as _lg
    _log = _lg.getLogger(__name__)
    _log.info("mfa_verify: officer=%s", officer.full_name)
    if not verify_otp(officer.mfa_secret, otp):
        _log.warning("mfa_verify FAILED: user=%s", officer.full_name)
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

    # Mark OTP as used (one-time-use replay protection)
    used_otps.add(otp)
    request.session["mfa_used_otps"] = list(used_otps)

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
    request.session.set_expiry(28800)

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

    now_ts = timezone.now().timestamp()
    time_limit_ts = now_ts - MFA_EMAIL_RATE_LIMIT_SECONDS
    last_sent_ts = request.session.get("mfa_last_sent_ts")

    if not last_sent_ts or last_sent_ts < time_limit_ts:
        otp = generate_otp(officer.mfa_secret)
        request.session["mfa_last_sent_ts"] = now_ts
        request.session.set_expiry(600)
        threading.Thread(target=send_mfa_email, args=(officer, otp), daemon=True).start()
        return JsonResponse({
            "ok": True,
            "message": "Verification code sent via email.",
            "delivery": "email",
        })

    remaining = int(MFA_EMAIL_RATE_LIMIT_SECONDS - (now_ts - last_sent_ts))
    return JsonResponse({
        "ok": False,
        "error": f"Email OTP was recently sent. Please wait {remaining} seconds.",
        "rate_limited": True,
    }, status=429)


@require_POST
@csrf_protect
def mfa_enable(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"ok": True, "message": "MFA is always enabled."})


@require_POST
@csrf_protect
def mfa_disable(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"ok": False, "error": "MFA cannot be disabled."}, status=403)


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

    if not officer.mfa_secret:
        officer.mfa_secret = encrypt_secret(generate_mfa_secret())
        officer.save(update_fields=["mfa_secret"])

    action = (request.POST.get("action") or "").strip()

    otp = generate_otp(officer.mfa_secret)
    logger.info(
        "ZT challenge: officer=%s action=%s",
        officer.full_name, action or "none",
    )
    request.session["zero_trust_otp"] = {
        "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat(),
    }

    threading.Thread(target=send_mfa_email, args=(officer, otp), kwargs={"action": action}, daemon=True).start()
    return JsonResponse({
        "ok": True,
        "message": "Verification code sent via email.",
        "delivery": "email",
        "sent": True,
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