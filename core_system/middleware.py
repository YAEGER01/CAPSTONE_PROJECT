from django.conf import settings
import logging
from datetime import timedelta
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from core_system.models import AccessSession

logger = logging.getLogger(__name__)

SESSION_IDLE_TIMEOUT = timedelta(minutes=30)


class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG:
            if request.path.startswith(("/static/", "/media/")):
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
            elif isinstance(response, HttpResponseRedirect):
                return response
            elif response.get("Content-Type", "").startswith("text/html"):
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
        return response


class ZeroTrustMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if (
            path.startswith(settings.STATIC_URL)
            or path.startswith(settings.MEDIA_URL)
            or path.startswith("/api/auth/")
            or path in ["/login/", "/"]
        ):
            return self.get_response(request)

        token = request.session.get("access_token")
        if token:
            try:
                session = AccessSession.objects.select_related("user_id_FK").get(token_id=token)
                
                # Check if session is revoked or expired
                if (
                    session.session_status != "Active"
                    or session.expires_at <= timezone.now()
                ):
                    # Session is no longer valid - clear it and redirect to login
                    request.session.flush()
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            "ok": False,
                            "session_expired": True,
                            "error": "Your session has been revoked due to a new login on another device. Please login again."
                        }, status=401)
                    return HttpResponseRedirect("/login/?session=revoked")

                now = timezone.now()

                # Idle timeout: no activity for SESSION_IDLE_TIMEOUT -> expire session
                if session.last_activity_at is not None:
                    if now - session.last_activity_at > SESSION_IDLE_TIMEOUT:
                        request.session.flush()
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                "ok": False,
                                "session_expired": True,
                                "error": "Your session has expired due to inactivity. Please login again."
                            }, status=401)
                        return HttpResponseRedirect("/login/?session=idle")

                current_ua = request.META.get("HTTP_USER_AGENT") or ""
                current_ip = request.META.get("REMOTE_ADDR") or "0.0.0.0"

                # If device or IP changes, or it's not verified yet
                device_changed = session.device_info and current_ua != session.device_info
                ip_changed = session.ip_address and current_ip != session.ip_address

                if device_changed or ip_changed:
                    logger.warning("Zero Trust Validation Failed: Device/IP Mismatch.")
                    session.trusted_device = False
                    session.save(update_fields=["trusted_device"])
                    response = JsonResponse({
                        "ok": False,
                        "zero_trust_challenge": True,
                        "error": "Zero Trust validation failed. Re-verification required."
                    }, status=403)
                    response["X-Zero-Trust-Challenge"] = "true"
                    return response

                # Continuous activity tracking (throttled to once per minute)
                if session.last_activity_at is None or now - session.last_activity_at > timedelta(minutes=1):
                    session.last_activity_at = now
                    session.save(update_fields=["last_activity_at"])

            except AccessSession.DoesNotExist:
                # Session doesn't exist - clear session data
                request.session.flush()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        "ok": False,
                        "session_expired": True,
                        "error": "Your session has been revoked. Please login again."
                    }, status=401)
                return HttpResponseRedirect("/login/?session=invalid")

        return self.get_response(request)

