from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from core_system.models import AccessSession


def logout_view(request: HttpRequest) -> HttpResponse:
    """Logout for custom session-token auth (revokes AccessSession + clears Django session keys)."""

    token = request.session.get("access_token")
    if token:
        try:
            sess = AccessSession.objects.get(token_id=token)
            sess.revoked_at = timezone.now()
            sess.session_status = "Revoked"
            sess.save(update_fields=["revoked_at", "session_status"])
        except AccessSession.DoesNotExist:
            # Token not found; continue with client-side logout
            pass

    request.session.pop("access_token", None)
    request.session.pop("officer_id", None)
    request.session.pop("role", None)

    return redirect("login")
