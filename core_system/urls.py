from django.urls import path
from . import views
from . import auditor_views
from . import treasurer_views
from . import president_views
from . import push_views
from . import settings_views
from . import report_views
from . import auditor_report_views
from . import fund_report_views
from . import htmx_views
from . import public_views
from . import auth_views


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
        "api/treasurer/officers/list/",
        treasurer_views.treasurer_officers_list,
        name="treasurer_officers_list",
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
    # --- Treasurer Monthly Dues OTC / Salary APIs ---
    path("api/treasurer/monthly-dues/add/", treasurer_views.treasurer_monthly_dues_add, name="treasurer_monthly_dues_add"),
    path("api/treasurer/monthly-dues/otc/add/", treasurer_views.treasurer_monthly_dues_otc_add, name="treasurer_monthly_dues_otc_add"),
    path("api/treasurer/monthly-dues/otc/list/", treasurer_views.treasurer_monthly_dues_otc_list, name="treasurer_monthly_dues_otc_list"),
    path("api/treasurer/monthly-dues/salary/add/", treasurer_views.treasurer_monthly_dues_salary_add, name="treasurer_monthly_dues_salary_add"),
    path("api/treasurer/monthly-dues/salary/list/", treasurer_views.treasurer_monthly_dues_salary_list, name="treasurer_monthly_dues_salary_list"),
    path("api/treasurer/monthly-dues/salary/bulk-preview/", treasurer_views.treasurer_salary_bulk_preview, name="treasurer_salary_bulk_preview"),
    path("api/treasurer/monthly-dues/salary/bulk-process/", treasurer_views.treasurer_salary_bulk_process, name="treasurer_salary_bulk_process"),
    path("api/treasurer/monthly-dues/salary/next-batch-ref/", treasurer_views.treasurer_next_batch_ref, name="treasurer_next_batch_ref"),
    path("api/treasurer/monthly-dues/tracking/", treasurer_views.treasurer_monthly_dues_tracking, name="treasurer_monthly_dues_tracking"),
    path(
        "api/treasurer/releases/list/",
        treasurer_views.treasurer_releases_list,
        name="treasurer_releases_list",
    ),
    path(
        "api/treasurer/dashboard/inflow-outflow/",
        treasurer_views.treasurer_dashboard_inflow_outflow,
        name="treasurer_dashboard_inflow_outflow",
    ),
    path(
        "api/treasurer/dashboard/monthly-flow/",
        treasurer_views.treasurer_monthly_flow,
        name="treasurer_monthly_flow",
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
    path(
        "api/treasurer/medical-aid/batch-add/",
        treasurer_views.treasurer_medical_aid_batch_add,
        name="treasurer_medical_aid_batch_add",
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
    path(
        "api/treasurer/members/batch-add/",
        treasurer_views.treasurer_member_batch_add,
        name="treasurer_member_batch_add",
    ),
    path(
        "api/treasurer/member/<int:member_id>/details/",
        treasurer_views.treasurer_member_details,
        name="treasurer_member_details",
    ),

    # --- Treasurer Payroll Batch APIs ---
    path(
        "api/treasurer/payroll-batches/create/",
        treasurer_views.treasurer_payroll_batch_create,
        name="treasurer_payroll_batch_create",
    ),
    path(
        "api/treasurer/payroll-batches/list/",
        treasurer_views.treasurer_payroll_batch_list,
        name="treasurer_payroll_batch_list",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/",
        treasurer_views.treasurer_payroll_batch_detail,
        name="treasurer_payroll_batch_detail",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/edit/",
        treasurer_views.treasurer_payroll_batch_edit,
        name="treasurer_payroll_batch_edit",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/delete/",
        treasurer_views.treasurer_payroll_batch_delete,
        name="treasurer_payroll_batch_delete",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/history/",
        treasurer_views.treasurer_payroll_batch_history,
        name="treasurer_payroll_batch_history",
    ),

    # --- Treasurer Department Visualization APIs ---
    path(
        "api/treasurer/department/member-stats/",
        treasurer_views.treasurer_member_stats_by_department,
        name="treasurer_member_stats_by_department",
    ),
    path(
        "api/treasurer/department/payment-tracking/",
        treasurer_views.treasurer_payment_tracking_by_department,
        name="treasurer_payment_tracking_by_department",
    ),
    path(
        "api/treasurer/department/financial-summary/",
        treasurer_views.treasurer_financial_summary_by_department,
        name="treasurer_financial_summary_by_department",
    ),
    path(
        "api/treasurer/department/aid-trends/",
        treasurer_views.treasurer_aid_trends_by_department,
        name="treasurer_aid_trends_by_department",
    ),
    path(
        "api/treasurer/department/payroll-analysis/",
        treasurer_views.treasurer_payroll_analysis_by_department,
        name="treasurer_payroll_analysis_by_department",
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
    # --- Auditor Payroll Batch APIs ---
    path(
        "api/auditor/pending-payroll-batches/",
        auditor_views.auditor_pending_payroll_batches,
        name="auditor_pending_payroll_batches",
    ),
    path(
        "api/auditor/payroll-batches/<int:batch_id>/",
        auditor_views.auditor_payroll_batch_detail,
        name="auditor_payroll_batch_detail",
    ),
    path(
        "api/auditor/payroll-batches/<int:batch_id>/verify/",
        auditor_views.auditor_verify_payroll_batch,
        name="auditor_verify_payroll_batch",
    ),
    path(
        "api/auditor/payroll-batches/<int:batch_id>/reject/",
        auditor_views.auditor_reject_payroll_batch,
        name="auditor_reject_payroll_batch",
    ),
    # --- President Workspace Endpoints ---
    path("president/", president_views.president_dashboard, name="president_dashboard"),
    path("api/president/officers/", president_views.president_officers_list, name="president_officers_list"),
    path("api/president/officers/create/", president_views.president_officers_create, name="president_officers_create"),
    path("api/president/officers/<int:officer_id>/update/", president_views.president_officers_update, name="president_officers_update"),
    path("api/president/officers/<int:officer_id>/reset-password/", president_views.president_officers_reset_password, name="president_officers_reset_password"),
    path("api/president/officers/<int:officer_id>/deactivate/", president_views.president_officers_deactivate, name="president_officers_deactivate"),
    path("api/president/profile/", president_views.president_profile, name="president_profile"),
    path("api/president/profile/update/", president_views.president_profile_update, name="president_profile_update"),
    path("api/president/officers/self-enroll/", president_views.president_officer_self_enroll, name="president_officer_self_enroll"),
    path("api/president/backups/", president_views.president_backups_list, name="president_backups_list"),
    path("api/president/backups/manual/", president_views.president_backups_manual, name="president_backups_manual"),
    path("api/president/backups/<int:job_id>/restore/", president_views.president_backups_restore, name="president_backups_restore"),
    # --- President Payroll Batch APIs ---
    path(
        "api/president/pending-payroll-batches/",
        president_views.president_pending_payroll_batches,
        name="president_pending_payroll_batches",
    ),
    path(
        "api/president/payroll-batches/<int:batch_id>/",
        president_views.president_payroll_batch_detail,
        name="president_payroll_batch_detail",
    ),
    path(
        "api/president/payroll-batches/<int:batch_id>/approve/",
        president_views.president_approve_payroll_batch,
        name="president_approve_payroll_batch",
    ),
    path(
        "api/president/payroll-batches/<int:batch_id>/reject/",
        president_views.president_reject_payroll_batch,
        name="president_reject_payroll_batch",
    ),
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
    # NOTE: approved-aid-posts is kept for the PayrollBatch UI to list active posts
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
    # DEPRECATED — replaced by PayrollBatch deductions
    # path("api/auditor/aid-post-member-pay/", auditor_views.auditor_aid_post_member_pay, name="auditor_aid_post_member_pay"),
    # path("api/auditor/aid-post-member-skip/", auditor_views.auditor_aid_post_member_skip, name="auditor_aid_post_member_skip"),
    # path("api/auditor/aid-post-finish/", auditor_views.auditor_aid_post_finish, name="auditor_aid_post_finish"),
    path(
        "api/auditor/aid-post-history/",
        auditor_views.auditor_aid_post_history,
        name="auditor_aid_post_history",
    ),
    path(
        "api/auditor/audited-logs/",
        auditor_views.auditor_audited_logs,
        name="auditor_audited_logs",
    ),
    path(
        "api/audit/trail/verify/",
        auditor_views.auditor_audit_trail_verify,
        name="audit_trail_verify_all",
    ),
    path(
        "api/audit/trail/verify/<str:table_name>/<int:record_id>/",
        auditor_views.auditor_audit_trail_verify,
        name="audit_trail_verify",
    ),
    # --- Treasurer Aid Tracking Post Endpoints ---
    # NOTE: approved-aid-posts is kept for the PayrollBatch UI to list active posts
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
    path("api/treasurer/aid-post-member-pay/", treasurer_views.treasurer_aid_post_member_pay, name="treasurer_aid_post_member_pay"),
    path("api/treasurer/aid-post-member-skip/", treasurer_views.treasurer_aid_post_member_skip, name="treasurer_aid_post_member_skip"),
    path("api/treasurer/aid-post-finish/", treasurer_views.treasurer_aid_post_finish, name="treasurer_aid_post_finish"),
    path("api/treasurer/aid-post-paid-with-funds/", treasurer_views.treasurer_aid_post_paid_with_funds, name="treasurer_aid_post_paid_with_funds"),
    path("api/treasurer/aid-post-member-notify/", treasurer_views.treasurer_aid_post_member_notify, name="treasurer_aid_post_member_notify"),
    path(
        "api/treasurer/aid-post-history/",
        treasurer_views.treasurer_aid_post_history,
        name="treasurer_aid_post_history",
    ),
    # --- Public (no-auth) Bylaws / Policy viewing for landing page ---
    path("api/public/bylaws/", public_views.public_bylaws, name="public_bylaws"),
    path(
        "api/public/bylaws/file/<int:document_id>/",
        public_views.public_bylaws_file,
        name="public_bylaws_file",
    ),
    path(
        "api/public/bylaws/render/<int:document_id>/",
        public_views.public_bylaws_render,
        name="public_bylaws_render",
    ),
    # --- Logout (custom officer session) ---
    path("logout/", views.logout_view, name="logout"),
    # --- Push Notification Subscriptions ---
    path("api/push/vapid-key/", push_views.vapid_public_key, name="push_vapid_key"),
    path("api/push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
    # --- System Settings API Endpoints ---
    path(
        "api/settings/grace-period/",
        settings_views.grace_period_setting,
        name="grace_period_setting",
    ),
    path(
        "api/settings/notifications/",
        settings_views.notification_settings,
        name="notification_settings",
    ),
    # --- Report API Endpoints ---
    path(
        "api/reports/overall/",
        report_views.download_overall_report,
        name="download_overall_report",
    ),
    path(
        "api/reports/department/<int:dept_id>/",
        report_views.download_department_report,
        name="download_department_report",
    ),
    path(
        "api/reports/contributions/",
        report_views.download_contribution_report,
        name="download_contribution_report",
    ),
    path(
        "api/treasurer/reports/generate/",
        report_views.generate_unified_report_view,
        name="generate_unified_report",
    ),
    # --- Auditor Report Endpoints ---
    path(
        "api/auditor/reports/create/",
        auditor_report_views.auditor_create_report,
        name="auditor_create_report",
    ),
    path(
        "api/auditor/reports/",
        auditor_report_views.auditor_reports_list,
        name="auditor_reports_list",
    ),
    path(
        "api/auditor/reports/<int:report_id>/",
        auditor_report_views.auditor_report_detail,
        name="auditor_report_detail",
    ),
    # --- President Report Approval Flow ---
    path(
        "api/president/auditor-reports/",
        auditor_report_views.president_auditor_reports_list,
        name="president_auditor_reports_list",
    ),
    path(
        "api/president/auditor-reports/<int:report_id>/approve/",
        auditor_report_views.president_approve_report,
        name="president_approve_report",
    ),
    path(
        "api/president/auditor-reports/<int:report_id>/request-revision/",
        auditor_report_views.president_request_report_revision,
        name="president_request_report_revision",
    ),
    # --- Treasurer: Organization Fund Report ---
    path(
        "api/treasurer/fund-reports/",
        fund_report_views.treasurer_fund_reports_list,
        name="treasurer_fund_reports_list",
    ),
    path(
        "api/treasurer/fund-reports/create/",
        fund_report_views.treasurer_create_fund_report,
        name="treasurer_create_fund_report",
    ),
    path(
        "api/treasurer/fund-reports/<int:report_id>/download/",
        fund_report_views.treasurer_download_fund_report,
        name="treasurer_download_fund_report",
    ),
    # --- Auditor: Fund Report Submission ---
    path(
        "api/auditor/fund-reports/",
        fund_report_views.auditor_fund_reports_list,
        name="auditor_fund_reports_list",
    ),
    path(
        "api/auditor/fund-reports/<int:report_id>/submit/",
        fund_report_views.auditor_submit_fund_report,
        name="auditor_submit_fund_report",
    ),
    # --- President: Fund Report Approval ---
    path(
        "api/president/fund-reports/",
        fund_report_views.president_fund_reports_list,
        name="president_fund_reports_list",
    ),
    path(
        "api/president/fund-reports/<int:report_id>/approve/",
        fund_report_views.president_approve_fund_report,
        name="president_approve_fund_report",
    ),
    path(
        "api/president/fund-reports/<int:report_id>/reject/",
        fund_report_views.president_reject_fund_report,
        name="president_reject_fund_report",
    ),
    # --- Treasurer: Mark Aid Post as Finished (sends to Auditor) ---
    path("api/treasurer/aid-post-upload-deduction-sheet/", treasurer_views.treasurer_aid_post_upload_deduction_sheet, name="treasurer_aid_post_upload_deduction_sheet"),
    path("api/treasurer/aid-post-record-remittance/", treasurer_views.treasurer_aid_post_record_remittance, name="treasurer_aid_post_record_remittance"),
    path("api/treasurer/aid-post-mark-finished/", treasurer_views.treasurer_aid_post_mark_finished, name="treasurer_aid_post_mark_finished"),
    # --- Treasurer: Release Aid Post (record fund in/out and close) ---
    path("api/treasurer/aid-post-release/", treasurer_views.treasurer_aid_post_release, name="treasurer_aid_post_release"),
    path("api/treasurer/aid-post-release-acknowledge/<int:post_id>/", treasurer_views.treasurer_aid_post_release_acknowledge, name="treasurer_aid_post_release_acknowledge"),
    path("api/treasurer/aid-post-close-repayment/", treasurer_views.treasurer_aid_post_close_repayment, name="treasurer_aid_post_close_repayment"),
    # --- Auditor: Aid Post Finish Verification ---
    path("api/auditor/pending-finish-requests/", auditor_views.auditor_pending_finish_requests, name="auditor_pending_finish_requests"),
    path("api/auditor/aid-post-verify-finish/", auditor_views.auditor_verify_post_finish, name="auditor_verify_post_finish"),
    path("api/auditor/finish-request-details/", auditor_views.auditor_finish_request_details, name="auditor_finish_request_details"),
    # --- President Aid Tracking Post Finish Approval ---
    path("api/president/aid-post-finish-requests/", president_views.president_pending_finish_requests, name="president_pending_finish_requests"),
    path("api/president/aid-post-finish-approve/", president_views.president_approve_aid_post_finish, name="president_approve_aid_post_finish"),
    path("api/president/aid-post-finish-reject/", president_views.president_reject_aid_post_finish, name="president_reject_aid_post_finish"),
    path("api/president/finish-request-details/", president_views.president_finish_request_details, name="president_finish_request_details"),
    # --- President ByLaws Constants Management ---
    path("api/president/pending-contributions/", president_views.president_pending_contributions, name="president_pending_contributions"),
    path("api/president/contribution-decision/", president_views.submit_presidential_contribution_decision, name="president_contribution_decision"),
    path("api/president/bylaws/constants/", president_views.get_policy_constants, name="president_bylaws_constants"),
    path("api/president/bylaws/constants/update/", president_views.update_policy_constant, name="president_bylaws_constant_update"),
    path("api/president/bylaws/files/", president_views.bylaws_files_api, name="president_bylaws_files"),
    path("api/president/bylaws/files/upload/", president_views.upload_bylaws_file, name="president_bylaws_file_upload"),
    path("api/president/bylaws/files/<int:document_id>/delete/", president_views.delete_bylaws_file, name="president_bylaws_file_delete"),

    # --- HTMX Partial Endpoints ---
    path(
        "hx/cash-flow-summary/",
        htmx_views.hx_cash_flow_summary,
        name="hx_cash_flow_summary",
    ),
    path(
        "hx/treasurer/module/<str:module_name>/",
        htmx_views.hx_treasurer_module,
        name="hx_treasurer_module",
    ),
    path(
        "hx/auditor/module/<str:module_name>/",
        htmx_views.hx_auditor_module,
        name="hx_auditor_module",
    ),
    path(
        "hx/president/module/<str:module_name>/",
        htmx_views.hx_president_module,
        name="hx_president_module",
    ),
    # --- Shared Fund Ledger & Transparency APIs ---
    path(
        "api/fund-ledger/",
        views.fund_ledger_list,
        name="fund_ledger_list",
    ),
    path(
        "api/fund-balance/",
        views.fund_balance_summary,
        name="fund_balance_summary",
    ),
    path(
        "api/member-deductions/",
        views.member_deductions_list,
        name="member_deductions_list",
    ),
    path(
        "api/member/<int:member_id>/deductions/",
        views.member_deductions_list,
        name="member_deductions_by_id",
    ),
    # --- MFA API ---
    path("api/auth/mfa/enable/", auth_views.mfa_enable, name="mfa_enable"),
    path("api/auth/mfa/disable/", auth_views.mfa_disable, name="mfa_disable"),
    path("api/auth/mfa/challenge/", auth_views.mfa_challenge, name="mfa_challenge"),
    path("api/auth/mfa/verify/", auth_views.mfa_verify, name="mfa_verify"),
    path("mfa/challenge/", auth_views.mfa_challenge_page, name="mfa_challenge_page"),
    path("api/auth/zero-trust/challenge/", auth_views.zero_trust_challenge, name="zero_trust_challenge"),
    path("api/auth/zero-trust/verify/", auth_views.zero_trust_verify, name="zero_trust_verify"),
    path("api/auth/zero-trust/status/", auth_views.zero_trust_status, name="zero_trust_status"),
    path("api/auth/term-info/", auth_views.term_info, name="term_info"),
]

handler403 = "core_system.president_views.permission_denied_view"
