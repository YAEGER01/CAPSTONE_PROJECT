from django.conf import settings
import logging
from django.http import JsonResponse
from django.utils import timezone
from core_system.models import AccessSession

logger = logging.getLogger(__name__)


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
                if (
                    session.session_status != "active"
                    or session.revoked_at is not None
                    or session.expires_at <= timezone.now()
                ):
                    return self.get_response(request)

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

            except AccessSession.DoesNotExist:
                pass

        return self.get_response(request)

