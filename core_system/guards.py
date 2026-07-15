from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
import logging

from core_system.models import AccessSession

logger = logging.getLogger(__name__)


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

        logger.warning(
            "require_officer_session: session not active: token=%s status=%s",
            token,
            sess.session_status,
        )
        return HttpResponseForbidden("Session is not active.")

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

    logger.warning(
        "require_role check: path=%s officer_role=%r targets=%r",
        getattr(request, "path", None),
        officer_role,
        targets,
    )

    if officer_role not in targets:
        raise PermissionDenied("Forbidden for this role.")

    return None
