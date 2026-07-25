from django.urls import re_path

from core_system.consumers import AuditorDashboardConsumer, TreasurerDashboardConsumer, PresidentDashboardConsumer

websocket_urlpatterns = [
    re_path(r"ws/auditor-dashboard/$", AuditorDashboardConsumer.as_asgi()),
    re_path(r"ws/treasurer-dashboard/$", TreasurerDashboardConsumer.as_asgi()),
    re_path(r"ws/president-dashboard/$", PresidentDashboardConsumer.as_asgi()),
]
