from django.urls import path
from . import views
from . import auditor_views
from . import treasurer_views
from . import president_views
from . import push_views


urlpatterns = [
    # --- Treasurer Workspace Endpoints ---
    path("treasurer/", treasurer_views.treasurer_dashboard, name="treasurer_dashboard"),
    # --- Treasurer Member Enrollment API ---
    # Frontend posts to: /api/treasurer/members/add/
    path(
        "api/treasurer/members/add/",
        treasurer_views.treasurer_add_member,
        name="treasurer_add_member",
    ),
    # --- Treasurer Members List API (for dashboard table rendering) ---
    path(
        "api/treasurer/members/list/",
        treasurer_views.treasurer_members_list,
        name="treasurer_members_list",
    ),
    path(
        "api/treasurer/members/active-count/",
        treasurer_views.treasurer_active_members_count,
        name="treasurer_active_members_count",
    ),
    path(
        "api/treasurer/records/requiring-revision/",
        treasurer_views.treasurer_records_requiring_revision,
        name="treasurer_records_requiring_revision",
    ),
    # --- Treasurer Membership Fee APIs ---
    path(
        "api/treasurer/membership-fees/add/",
        treasurer_views.treasurer_membership_fee_add,
        name="treasurer_membership_fee_add",
    ),
    path(
        "api/treasurer/membership-fees/list/",
        treasurer_views.treasurer_membership_fee_list,
        name="treasurer_membership_fee_list",
    ),
    path(
        "api/treasurer/membership-fees/returned/list/",
        treasurer_views.treasurer_membership_fees_returned_list,
        name="treasurer_membership_fees_returned_list",
    ),
    path(
        "api/treasurer/monthly-dues/returned/list/",
        treasurer_views.treasurer_monthly_dues_returned_list,
        name="treasurer_monthly_dues_returned_list",
    ),
    path(
        "api/treasurer/medical-aid/returned/list/",
        treasurer_views.treasurer_medical_aid_returned_list,
        name="treasurer_medical_aid_returned_list",
    ),
    path(
        "api/treasurer/death-aid/returned/list/",
        treasurer_views.treasurer_death_aid_returned_list,
        name="treasurer_death_aid_returned_list",
    ),
    path(
        "api/treasurer/approved-transactions-total/",
        treasurer_views.treasurer_approved_transactions_total,
        name="treasurer_approved_transactions_total",
    ),
    path(
        "api/cash-flow-summary/",
        treasurer_views.cash_flow_summary,
        name="cash_flow_summary",
    ),
    # --- Treasurer Monthly Dues (OTC) APIs ---
    path(
        "api/treasurer/monthly-dues/add/",
        treasurer_views.treasurer_monthly_dues_add,
        name="treasurer_monthly_dues_add",
    ),
    path(
        "api/treasurer/monthly-dues/otc/add/",
        treasurer_views.treasurer_monthly_dues_otc_add,
        name="treasurer_monthly_dues_otc_add",
    ),
    path(
        "api/treasurer/monthly-dues/otc/list/",
        treasurer_views.treasurer_monthly_dues_otc_list,
        name="treasurer_monthly_dues_otc_list",
    ),
    # --- Treasurer Monthly Dues (Salary Deduction) APIs ---
    path(
        "api/treasurer/monthly-dues/salary/add/",
        treasurer_views.treasurer_monthly_dues_salary_add,
        name="treasurer_monthly_dues_salary_add",
    ),
    path(
        "api/treasurer/monthly-dues/salary/list/",
        treasurer_views.treasurer_monthly_dues_salary_list,
        name="treasurer_monthly_dues_salary_list",
    ),
    path(
        "api/treasurer/monthly-dues/salary/bulk-preview/",
        treasurer_views.treasurer_salary_bulk_preview,
        name="treasurer_salary_bulk_preview",
    ),
    path(
        "api/treasurer/monthly-dues/salary/bulk-process/",
        treasurer_views.treasurer_salary_bulk_process,
        name="treasurer_salary_bulk_process",
    ),
    path(
        "api/treasurer/releases/list/",
        treasurer_views.treasurer_releases_list,
        name="treasurer_releases_list",
    ),
    path(
        "api/treasurer/aids/release/",
        treasurer_views.treasurer_release_aid,
        name="treasurer_release_aid",
    ),
    # --- Medical Aid (Claims) APIs ---
    path(
        "api/treasurer/medical-aid/add/",
        treasurer_views.treasurer_medical_aid_add,
        name="treasurer_medical_aid_add",
    ),
    path(
        "api/treasurer/medical-aids/list/",
        treasurer_views.treasurer_medical_aid_list,
        name="treasurer_medical_aid_list",
    ),
    # --- Death Aid (Claims) APIs ---
    path(
        "api/treasurer/death-aid/add/",
        treasurer_views.treasurer_death_aid_add,
        name="treasurer_death_aid_add",
    ),
    path(
        "api/treasurer/death-aids/list/",
        treasurer_views.treasurer_death_aids_list,
        name="treasurer_death_aids_list",
    ),
    # --- Treasurer Resubmit API ---
    path(
        "api/treasurer/resubmit/<str:table_name>/<int:record_id>/",
        treasurer_views.treasurer_resubmit_entry,
        name="treasurer_resubmit_entry",
    ),
    # --- Treasurer Member Update / Retire API ---
    path(
        "api/treasurer/members/update/",
        treasurer_views.treasurer_member_update,
        name="treasurer_member_update",
    ),
    path(
        "api/treasurer/members/retire/",
        treasurer_views.treasurer_member_retire,
        name="treasurer_member_retire",
    ),

    # --- Auditor Workspace Endpoints ---
    path("auditor/", auditor_views.auditor_dashboard, name="auditor_dashboard"),

    path(
        "api/auditor/pending-payments/list/",
        auditor_views.auditor_pending_payments,
        name="auditor_pending_payments",
    ),
    path(
        "api/auditor/pending-aids/list/",
        auditor_views.auditor_pending_aids,
        name="auditor_pending_aids",
    ),
    path(
        "api/auditor/verify-payment/",
        auditor_views.auditor_verify_payment,
        name="auditor_verify_payment",
    ),
    path(
        "api/auditor/verify-aid/",
        auditor_views.auditor_verify_aid,
        name="auditor_verify_aid",
    ),
    path(
        "api/auditor/pending-membership-fees/list/",
        auditor_views.auditor_pending_membership_fees,
        name="auditor_pending_membership_fees",
    ),
    path(
        "api/auditor/verify-membership-fee/",
        auditor_views.auditor_verify_membership_fee,
        name="auditor_verify_membership_fee",
    ),
    path(
        "api/auditor/verify-membership-fee/batch/",
        auditor_views.auditor_verify_membership_fee_batch,
        name="auditor_verify_membership_fee_batch",
    ),
    path(
        "api/auditor/verify-batch/",
        auditor_views.auditor_verify_batch,
        name="auditor_verify_batch",
    ),
    path(
        "api/auditor/reject/",
        auditor_views.reject_transaction,
        name="auditor_reject_transaction",
    ),
    path(
        "api/auditor/supporting-proof/<str:model_type>/<int:record_id>/",
        auditor_views.auditor_supporting_proof,
        name="auditor_supporting_proof",
    ),
    # --- President Workspace Endpoints ---
    path("president/", president_views.president_dashboard, name="president_dashboard"),
    # --- President: auditor-approved payments display ---
    path(
        "api/president/auditor-approved-payments/list/",
        president_views.president_auditor_approved_payments_queue,
        name="president_auditor_approved_payments_queue",
    ),
    path(
        "api/president/auditor-approved-payments/detail/<int:entity_id>/",
        president_views.president_auditor_approved_payment_detail,
        name="president_auditor_approved_payment_detail",
    ),
    path(
        "api/president/auditor-approved-aids/list/",
        president_views.president_auditor_approved_aids_queue,
        name="president_auditor_approved_aids_queue",
    ),
    path(
        "api/payments/presidential-queue/",
        president_views.get_pending_presidential_payments,
        name="presidential_queue",
    ),
    path(
        "api/payments/presidential-decision/",
        president_views.submit_presidential_decision,
        name="presidential_decision",
    ),
    path(
        "api/payments/presidential-decision/batch/",
        president_views.submit_presidential_decision_batch,
        name="presidential_decision_batch",
    ),
    path(
        "api/aids/presidential-decision/",
        president_views.submit_presidential_aid_decision,
        name="presidential_aid_decision",
    ),
    path(
        "api/aids/presidential-decision/batch/",
        president_views.submit_presidential_aid_decision_batch,
        name="presidential_aid_decision_batch",
    ),
    path(
        "api/audit/trail/<str:table_name>/<int:record_id>/",
        president_views.audit_trail_api,
        name="audit_trail_api",
    ),
    path(
        "api/president/kpi-counts/",
        president_views.president_kpi_counts,
        name="president_kpi_counts",
    ),
    # --- Auditor Aid Tracking Post Endpoints ---
    path(
        "api/auditor/approved-aid-posts/",
        auditor_views.auditor_approved_aid_posts,
        name="auditor_approved_aid_posts",
    ),
    path(
        "api/auditor/aid-post-members/<int:post_id>/",
        auditor_views.auditor_aid_post_members,
        name="auditor_aid_post_members",
    ),
    path(
        "api/auditor/aid-post-member-pay/",
        auditor_views.auditor_aid_post_member_pay,
        name="auditor_aid_post_member_pay",
    ),
    path(
        "api/auditor/aid-post-member-skip/",
        auditor_views.auditor_aid_post_member_skip,
        name="auditor_aid_post_member_skip",
    ),
    path(
        "api/auditor/aid-post-member-notify/",
        auditor_views.auditor_aid_post_member_notify,
        name="auditor_aid_post_member_notify",
    ),
    path(
        "api/auditor/aid-post-finish/",
        auditor_views.auditor_aid_post_finish,
        name="auditor_aid_post_finish",
    ),
    path(
        "api/auditor/aid-post-history/",
        auditor_views.auditor_aid_post_history,
        name="auditor_aid_post_history",
    ),
    # --- Treasurer Aid Tracking Post Endpoints ---
    path(
        "api/treasurer/approved-aid-posts/",
        treasurer_views.treasurer_approved_aid_posts,
        name="treasurer_approved_aid_posts",
    ),
    path(
        "api/treasurer/aid-post-members/<int:post_id>/",
        treasurer_views.treasurer_aid_post_members,
        name="treasurer_aid_post_members",
    ),
    path(
        "api/treasurer/aid-post-member-pay/",
        treasurer_views.treasurer_aid_post_member_pay,
        name="treasurer_aid_post_member_pay",
    ),
    path(
        "api/treasurer/aid-post-member-skip/",
        treasurer_views.treasurer_aid_post_member_skip,
        name="treasurer_aid_post_member_skip",
    ),
    path(
        "api/treasurer/aid-post-member-notify/",
        treasurer_views.treasurer_aid_post_member_notify,
        name="treasurer_aid_post_member_notify",
    ),
    path(
        "api/treasurer/aid-post-finish/",
        treasurer_views.treasurer_aid_post_finish,
        name="treasurer_aid_post_finish",
    ),
    path(
        "api/treasurer/aid-post-history/",
        treasurer_views.treasurer_aid_post_history,
        name="treasurer_aid_post_history",
    ),
    # --- Logout (custom officer session) ---
    path("logout/", views.logout_view, name="logout"),
    # --- Push Notification Subscriptions ---
    path("api/push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
]
handler403 = "core_system.president_views.permission_denied_view"
