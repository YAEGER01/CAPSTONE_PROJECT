from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied

from core_system.models import AccessSession


def require_officer_session(request: HttpRequest) -> HttpResponse | None:
    """Validate ACCESS_SESSION token stored in session.

    Returns:
      - None if authorized
      - redirect("login") or HttpResponseForbidden otherwise
    """

    token = request.session.get("access_token")
    if not token:
        return redirect("login")

    try:
        sess = AccessSession.objects.get(token_id=token)
    except AccessSession.DoesNotExist:
        request.session.pop("access_token", None)
        return redirect("login")

    if sess.revoked_at is not None:
        request.session.pop("access_token", None)
        return redirect("login")

    # `expires_at` is required in schema.
    from django.utils import timezone

    now = timezone.now()
    if sess.expires_at <= now:
        request.session.pop("access_token", None)
        return redirect("login")

    if (sess.session_status or "").lower() != "active":
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Session is not active.")

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

    if officer_role not in targets:
        raise PermissionDenied("Forbidden for this role.")

    return None
