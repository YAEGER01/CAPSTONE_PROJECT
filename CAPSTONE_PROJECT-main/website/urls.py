from django.urls import path

from . import views


urlpatterns = [
    path("", views.home_view, name="home"),
    path("login/", views.portal_login_view, name="portal-login"),
    path("register/", views.portal_register_view, name="portal-register"),
    path("logout/", views.portal_logout_view, name="portal-logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("api/update-member-profile/", views.update_member_profile_view, name="update-member-profile"),
    path("officer-dashboard/", views.officer_dashboard_view, name="officer-dashboard"),
    path("president-dashboard/", views.president_dashboard_view, name="president-dashboard"),
    path("secretary-dashboard/", views.secretary_dashboard_view, name="secretary-dashboard"),
    path("attendance-dashboard/", views.attendance_dashboard_view, name="attendance-dashboard"),
    path("business-manager-dashboard/", views.business_manager_dashboard_view, name="business-manager-dashboard"),
    path("treasurer-dashboard/", views.treasurer_dashboard_view, name="treasurer-dashboard"),
    path("auditor-dashboard/", views.auditor_dashboard_view, name="auditor-dashboard"),
    path("super-admin/", views.super_admin_dashboard_view, name="super-admin"),
    
    # Finance Module
    path("finance/income/", views.finance_income_expenses_view, name="finance-income"),
    path("finance/fees/", views.finance_membership_fees_view, name="finance-fees"),
    path("finance/budget/", views.finance_budget_view, name="finance-budget"),
    path("finance/reports/", views.finance_reports_view, name="finance-reports"),
    path("finance/receipts/", views.finance_receipts_view, name="finance-receipts"),
    
    # Documents Module
    path("documents/memos/", views.documents_memos_view, name="documents-memos"),
    path("documents/minutes/", views.documents_minutes_view, name="documents-minutes"),
    path("documents/archive/", views.documents_archive_view, name="documents-archive"),
    path("documents/announcements/", views.documents_announcements_view, name="documents-announcements"),
    path("documents/official/", views.documents_official_view, name="documents-official"),
    
    # Attendance Module
    path("attendance/qr/", views.attendance_qr_view, name="attendance-qr"),
    path("attendance/monitor/", views.attendance_monitor_view, name="attendance-monitor"),
    path("attendance/events/", views.attendance_events_view, name="attendance-events"),
    path("attendance/export/", views.attendance_export_view, name="attendance-export"),
    
    # Members Module
    path("members/add/", views.members_add_view, name="members-add"),
    path("members/profiles/", views.members_profiles_view, name="members-profiles"),
    path("members/status/", views.members_status_view, name="members-status"),
    path("members/history/", views.members_history_view, name="members-history"),
    
    # Admin
    path("approvals/", views.approvals_view, name="approvals"),
    path("analytics/", views.analytics_view, name="analytics"),
    
    # Public pages
    path("about/", views.about_view, name="about"),
    path("members-list/", views.members_view, name="members"),
    path("contact/", views.contact_view, name="contact"),
]
