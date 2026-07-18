from __future__ import annotations

from datetime import timedelta
import json
import threading

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from functools import wraps
import logging

from core_system.models import AccessSession

logger = logging.getLogger(__name__)


def _send_session_expired_push(officer) -> None:
    """Send a push notification to all of the officer's subscribed devices."""
    try:
        from core_system.models import PushSubscription
        from pywebpush import webpush

        subs = PushSubscription.objects.filter(officer_id_FK=officer)
        if not subs.exists():
            return

        vapid_private_key = settings.VAPID_PRIVATE_KEY
        vapid_aud = getattr(settings, "PUSH_VAPID_AUD", "http://127.0.0.1:8000")

        payload = json.dumps({
            "title": "Session Expired",
            "body": "You have been logged out due to inactivity.",
            "url": "/",
        })

        for sub in subs:
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
                        "aud": vapid_aud,
                    },
                )
            except Exception as exc:
                logger.warning("Session-expired push failed for sub %s: %s", sub.pk, exc)
    except Exception as exc:
        logger.warning("Session-expired push setup failed: %s", exc)


def require_officer_session(request: HttpRequest) -> HttpResponse | None:
    """Validate ACCESS_SESSION token stored in session.

    Returns:
      - None if authorized
      - redirect to landing page with session_expired param otherwise
    """

    token = request.session.get("access_token")
    if not token:
        return redirect("/?session_expired=1")

    try:
        sess = AccessSession.objects.select_related("user_id_FK").get(token_id=token)
    except AccessSession.DoesNotExist:
        request.session.pop("access_token", None)
        return redirect("/?session_expired=1")

    if sess.revoked_at is not None:
        officer = sess.user_id_FK
        request.session.pop("access_token", None)
        threading.Thread(target=_send_session_expired_push, args=(officer,), daemon=True).start()
        return redirect("/?session_expired=1")

    now = timezone.now()
    if sess.expires_at <= now:
        officer = sess.user_id_FK
        request.session.pop("access_token", None)
        threading.Thread(target=_send_session_expired_push, args=(officer,), daemon=True).start()
        return redirect("/?session_expired=1")

    if (sess.session_status or "").lower() != "active":
        officer = sess.user_id_FK
        logger.warning(
            "require_officer_session: session not active: token=%s status=%s",
            token,
            sess.session_status,
        )
        request.session.pop("access_token", None)
        threading.Thread(target=_send_session_expired_push, args=(officer,), daemon=True).start()
        return redirect("/?session_expired=1")

    logger.debug("require_officer_session passed for token=%s", token)
    return None


def require_role(request: HttpRequest, *, role: str | list[str] | None) -> HttpResponse | None:
    """Require authenticated officer session and matching role(s)."""

    guard = require_officer_session(request)
    if guard is not None:
        return guard

    if role is None:
        return None

    officer_role = (request.session.get("role") or "").strip().lower()
    roles = [role] if isinstance(role, str) else role
    targets = [r.strip().lower() for r in roles]

    if not officer_role:
        token = request.session.get("access_token")
        if token:
            try:
                sess = AccessSession.objects.get(token_id=token)
                officer_role = (sess.user_id_FK.role or "").strip().lower()
            except AccessSession.DoesNotExist:
                officer_role = ""

    logger.debug(
        "require_role check: path=%s officer_role=%r targets=%r",
        getattr(request, "path", None),
        officer_role,
        targets,
    )

    if officer_role not in targets:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accepts("application/json"):
            return JsonResponse({"ok": False, "error": "Forbidden for this role."}, status=403)
        raise PermissionDenied("Forbidden for this role.")

    return None


_ZT_TIMEOUTS = {
    "read": None,
    "verify": timedelta(minutes=15),
    "approve": timedelta(minutes=5),
}


def _zt_challenge_response(level: str) -> JsonResponse:
    response = JsonResponse({
        "ok": False,
        "zero_trust_challenge": True,
        "error": f"Zero Trust verification required for {level} access.",
    }, status=403)
    response["X-Zero-Trust-Challenge"] = "true"
    return response


def check_zero_trust(request: HttpRequest, level: str = "verify") -> HttpResponse | None:
    """Inline guard: returns None if allowed, or an error response if ZT challenge needed.

    Use inside view functions alongside require_role():
        guard = check_zero_trust(request, level="approve")
        if guard is not None:
            return guard
    """
    token = request.session.get("access_token")
    if not token:
        return redirect("/?session_expired=1")

    try:
        sess = AccessSession.objects.select_related("user_id_FK").get(token_id=token)
    except AccessSession.DoesNotExist:
        request.session.pop("access_token", None)
        return redirect("/?session_expired=1")

    if level == "read":
        return None

    if not sess.trusted_device:
        return _zt_challenge_response(level)

    timeout = _ZT_TIMEOUTS.get(level)
    if timeout is not None:
        policy = sess.session_policy or {}
        verified_at_str = policy.get("zt_verified_at")
        if verified_at_str:
            try:
                verified_at = timezone.datetime.fromisoformat(verified_at_str)
                if timezone.is_naive(verified_at):
                    verified_at = timezone.make_aware(verified_at)
                if timezone.now() - verified_at > timeout:
                    return _zt_challenge_response(level)
            except (ValueError, TypeError):
                return _zt_challenge_response(level)
        else:
            return _zt_challenge_response(level)

    return None


def require_zero_trust(level="verify"):
    """Decorator: require Zero Trust verification at the given level.

    Usage:
        @require_zero_trust(level="approve")
        def my_view(request):
            ...
    """
    if callable(level):
        func = level
        level = "verify"
        return require_zero_trust(level)(func)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            guard = require_officer_session(request)
            if guard is not None:
                return guard

            guard = check_zero_trust(request, level=level)
            if guard is not None:
                return guard

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

