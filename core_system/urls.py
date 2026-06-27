from django.urls import path
from . import views
from . import views_members_api
from . import views_auditor_api
from . import member_api


urlpatterns = [
    # --- Treasurer Workspace Endpoints ---
    path("treasurer/", views.treasurer_dashboard, name="treasurer_dashboard"),
    # --- Treasurer Member Enrollment API ---
    # Frontend posts to: /api/treasurer/members/add/
    path(
        "api/treasurer/members/add/",
        views.treasurer_add_member,
        name="treasurer_add_member",
    ),
    # --- Treasurer Members List API (for dashboard table rendering) ---
    path(
        "api/treasurer/members/list/",
        views_members_api.treasurer_members_list,
        name="treasurer_members_list",
    ),
    path(
        "api/treasurer/members/active-count/",
        views_members_api.treasurer_active_members_count,
        name="treasurer_active_members_count",
    ),
    path(
        "api/treasurer/records/requiring-revision/",
        views_members_api.treasurer_records_requiring_revision,
        name="treasurer_records_requiring_revision",
    ),
    # --- Treasurer Membership Fee APIs ---
    path(
        "api/treasurer/membership-fees/add/",
        views.treasurer_membership_fee_add,
        name="treasurer_membership_fee_add",
    ),
    path(
        "api/treasurer/membership-fees/list/",
        views.treasurer_membership_fee_list,
        name="treasurer_membership_fee_list",
    ),
    path(
        "api/treasurer/membership-fees/returned/list/",
        views.treasurer_membership_fees_returned_list,
        name="treasurer_membership_fees_returned_list",
    ),
    path(
        "api/treasurer/monthly-dues/returned/list/",
        views.treasurer_monthly_dues_returned_list,
        name="treasurer_monthly_dues_returned_list",
    ),
    path(
        "api/treasurer/approved-transactions-total/",
        views.treasurer_approved_transactions_total,
        name="treasurer_approved_transactions_total",
    ),
    # --- Treasurer Monthly Dues (OTC) APIs ---
    path(
        "api/treasurer/monthly-dues/otc/add/",
        views.treasurer_monthly_dues_otc_add,
        name="treasurer_monthly_dues_otc_add",
    ),
    path(
        "api/treasurer/monthly-dues/otc/list/",
        views.treasurer_monthly_dues_otc_list,
        name="treasurer_monthly_dues_otc_list",
    ),
    # --- Treasurer Monthly Dues (Salary Deduction) APIs ---
    path(
        "api/treasurer/monthly-dues/salary/add/",
        views.treasurer_monthly_dues_salary_add,
        name="treasurer_monthly_dues_salary_add",
    ),
    path(
        "api/treasurer/monthly-dues/salary/list/",
        views.treasurer_monthly_dues_salary_list,
        name="treasurer_monthly_dues_salary_list",
    ),
    # --- Medical Aid (Claims) APIs ---
    path(
        "api/treasurer/medical-aid/add/",
        views.treasurer_medical_aid_add,
        name="treasurer_medical_aid_add",
    ),
    path(
        "api/treasurer/medical-aids/list/",
        views.treasurer_medical_aid_list,
        name="treasurer_medical_aid_list",
    ),
    # --- Death Aid (Claims) APIs ---
    path(
        "api/treasurer/death-aid/add/",
        views.treasurer_death_aid_add,
        name="treasurer_death_aid_add",
    ),
    path(
        "api/treasurer/death-aids/list/",
        views.treasurer_death_aids_list,
        name="treasurer_death_aids_list",
    ),
    # --- Treasurer Resubmit API ---
    path(
        "api/treasurer/resubmit/<str:table_name>/<int:record_id>/",
        views.treasurer_resubmit_entry,
        name="treasurer_resubmit_entry",
    ),
    # --- Treasurer Member Update / Retire API ---
    path(
        "api/treasurer/members/update/",
        member_api.treasurer_member_update,
        name="treasurer_member_update",
    ),
    path(
        "api/treasurer/members/retire/",
        member_api.treasurer_member_retire,
        name="treasurer_member_retire",
    ),

    # --- Auditor Workspace Endpoints ---
    path("auditor/", views.auditor_dashboard, name="auditor_dashboard"),

    path(
        "api/auditor/pending-payments/list/",
        views_auditor_api.auditor_pending_payments,
        name="auditor_pending_payments",
    ),
    path(
        "api/auditor/pending-aids/list/",
        views_auditor_api.auditor_pending_aids,
        name="auditor_pending_aids",
    ),
    path(
        "api/auditor/verify-payment/",
        views_auditor_api.auditor_verify_payment,
        name="auditor_verify_payment",
    ),
    path(
        "api/auditor/verify-aid/",
        views_auditor_api.auditor_verify_aid,
        name="auditor_verify_aid",
    ),
    path(
        "api/auditor/pending-membership-fees/list/",
        views_auditor_api.auditor_pending_membership_fees,
        name="auditor_pending_membership_fees",
    ),
    path(
        "api/auditor/verify-membership-fee/",
        views_auditor_api.auditor_verify_membership_fee,
        name="auditor_verify_membership_fee",
    ),
    path(
        "api/auditor/reject/",
        views_auditor_api.reject_transaction,
        name="auditor_reject_transaction",
    ),
    path(
        "api/auditor/supporting-proof/<str:model_type>/<int:record_id>/",
        views_auditor_api.auditor_supporting_proof,
        name="auditor_supporting_proof",
    ),
    # --- President Workspace Endpoints ---
    path("president/", views.president_dashboard, name="president_dashboard"),
    # --- President: auditor-approved payments display ---
    path(
        "api/president/auditor-approved-payments/list/",
        views_auditor_api.president_auditor_approved_payments_queue,
        name="president_auditor_approved_payments_queue",
    ),
    path(
        "api/president/auditor-approved-payments/detail/<int:entity_id>/",
        views_auditor_api.president_auditor_approved_payment_detail,
        name="president_auditor_approved_payment_detail",
    ),
    path(
        "api/payments/presidential-queue/",
        views.get_pending_presidential_payments,
        name="presidential_queue",
    ),
    path(
        "api/payments/presidential-decision/",
        views.submit_presidential_decision,
        name="presidential_decision",
    ),
    # --- Logout (custom officer session) ---
    path("logout/", views.logout_view, name="logout"),
]
handler403 = "core_system.views.permission_denied_view"
