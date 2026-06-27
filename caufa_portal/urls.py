# caufa_portal/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from core_system.auth_views import officer_login

from django.views.generic import TemplateView  # Allows rendering your index directly

urlpatterns = [
    path("admin/", admin.site.urls),
    # 1. Main Landing: Shows your index.html homepage immediately at http://127.0.0.1:8000/
    path("", TemplateView.as_view(template_name="website/index.html"), name="home"),
    # 2. Login Portal: Moved to http://127.0.0.1:8000/login/
    path(
        "login/",
        officer_login,
        name="login",
    ),
    # Treasurer workspace + internal module fragments
    path("", include("core_system.urls")),
]

# Serve uploaded media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "core_system.views.permission_denied_view"
