from django.http import Http404
from django.shortcuts import render

from core_system.guards import require_role
from core_system.logout_view import logout_view

# ==========================================================================
# TREASURER WORKSPACE VIEWS
# ==========================================================================


def treasurer_dashboard(request):
    """Loads the main workspace shell frame for the Treasurer role route context."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard
    return render(request, "website/Treasurer/base.html")


def get_treasurer_module(request, module_name):
    """Serves inner dashboard layout modules dynamically from the isolated subfolder path."""
    valid_modules = ["create_entry", "ledger_view", "draft_manager", "profile"]

    if module_name == "profile":
        return render(request, "website/Profile/profile_module.html")

    if module_name in valid_modules:
        return render(request, f"website/Treasurer/module/{module_name}.html")

    raise Http404(
        "Requested module fragment does not exist inside Treasurer workspace domain."
    )


# ==========================================================================
# AUDITOR WORKSPACE VIEWS
# ==========================================================================


def auditor_dashboard(request):
    """Loads the main workspace shell frame for the Auditor role route context."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    return render(request, "website/Auditor/base.html")


def get_auditor_module(request, module_name):
    """Serves inner dashboard layout modules dynamically from the isolated subfolder path."""
    valid_modules = [
        "verification_queue",
        "global_ledger",
        "immutable_audit_log",
        "profile",
    ]

    if module_name == "profile":
        return render(request, "website/Profile/profile_module.html")

    if module_name in valid_modules:
        return render(request, f"website/Auditor/module/{module_name}.html")

    raise Http404(
        "Requested module fragment does not exist inside Auditor workspace domain."
    )


# ==========================================================================
# PRESIDENT WORKSPACE VIEWS
# ==========================================================================


def president_dashboard(request):
    """Loads the main workspace shell frame for the President role route context."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    return render(request, "website/President/base.html")


def get_president_module(request, module_name):
    """Serves inner dashboard layout modules dynamically from the isolated subfolder path."""
    valid_modules = [
        "approval_queue",
        "publication_center",
        "executive_ledger",
        "system_audit_log",
        "profile",
    ]

    if module_name == "profile":
        return render(request, "website/Profile/profile_module.html")

    if module_name in valid_modules:
        return render(request, f"website/President/module/{module_name}.html")

    raise Http404(
        "Requested module fragment does not exist inside President workspace domain."
    )


def permission_denied_view(request, exception=None):
    """
    Global interceptor engine for 403 Forbidden events.
    Renders our custom institutional access alert page.
    """
    return render(request, "errors/403.html", status=403)
