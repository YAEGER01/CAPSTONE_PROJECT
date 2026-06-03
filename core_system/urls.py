from django.urls import path
from . import views

urlpatterns = [
    # --- Treasurer Workspace Endpoints ---
    path("treasurer/", views.treasurer_dashboard, name="treasurer_dashboard"),
    path(
        "get-treasurer-module/<str:module_name>/",
        views.get_treasurer_module,
        name="get_treasurer_module",
    ),
    # --- Auditor Workspace Endpoints ---
    path("auditor/", views.auditor_dashboard, name="auditor_dashboard"),
    path(
        "get-auditor-module/<str:module_name>/",
        views.get_auditor_module,
        name="get_auditor_module",
    ),
    # --- President Workspace Endpoints ---
    path("president/", views.president_dashboard, name="president_dashboard"),
    path(
        "get-president-module/<str:module_name>/",
        views.get_president_module,
        name="get_president_module",
    ),
    # --- Logout (custom officer session) ---
    path("logout/", views.logout_view, name="logout"),
]
handler403 = "core_system.views.permission_denied_view"
