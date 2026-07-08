from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.db.models import Sum
from django.views.decorators.cache import never_cache

from core_system.guards import require_officer_session, require_role
from core_system.models import TransactionArchive, Contribution
from core_system.models import AidTrackingPost, Member, MembershipFee, OfficerUser, MonthlyDues, TransactionVerification
from core_system.constants.policy_constants import get_expected_dues_amount

import logging
logger = logging.getLogger(__name__)


@never_cache
def hx_cash_flow_summary(request: HttpRequest):
    guard = require_officer_session(request)
    if guard:
        return guard

    funds_in = sum(
        float(e.amount or 0)
        for e in TransactionArchive.objects.filter(
            transaction_type__in=["membership_fee", "monthly_dues"],
        )
    )

    funds_out = sum(
        float(e.amount or 0)
        for e in TransactionArchive.objects.filter(
            transaction_type__in=["medical_aid", "death_aid"],
        )
    )

    pending = (
        Contribution.objects.filter(
            status="NOT_PAID",
            aid_tracking_post_id_FK__is_active=True,
        ).aggregate(total=Sum("expected_amount"))["total"]
        or 0
    )

    return render(request, "htmx/cash_flow_fragment.html", {
        "funds_in": float(funds_in),
        "funds_out": float(funds_out),
        "pending_contributions": float(pending),
    })


TREASURER_MODULE_WHITELIST = {
    "dashboard-overview", "view-member-profile", "view-fee-payment",
    "view-returned-entries", "view-otc-payment", "view-salary-deduction",
    "view-monthly-dues-returned", "view-dues-tracking", "view-medical-aid",
    "view-death-aid", "view-medical-aid-returned", "view-death-aid-returned",
    "treasurer-aid-tracking-posts", "treasurer-aid-history", "view-reports",
}


@never_cache
def hx_treasurer_module(request: HttpRequest, module_name: str):
    guard = require_role(request, role="treasurer")
    if guard:
        return guard

    if module_name not in TREASURER_MODULE_WHITELIST:
        return HttpResponse(status=404)

    officer_id = request.session.get("officer_id")
    officer_full_name = ""
    officer_role = "treasurer"
    if officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "expected_dues_default_amount": get_expected_dues_amount(),
        "access_token": request.session.get("access_token", ""),
        "returned_entries_count": TransactionVerification.objects.filter(
            table_name="membership_fee",
            verification_status="Returned for Revision",
        ).count(),
        "monthly_dues_returned_count": TransactionVerification.objects.filter(
            table_name="monthly_dues",
            verification_status="Returned for Revision",
        ).count(),
        "medical_aid_returned_count": TransactionVerification.objects.filter(
            table_name="medical_aid",
            verification_status="Returned for Revision",
        ).count(),
        "death_aid_returned_count": TransactionVerification.objects.filter(
            table_name="death_aid",
            verification_status="Returned for Revision",
        ).count(),
        "active_aid_posts_count": AidTrackingPost.objects.filter(
            is_active=True,
        ).count(),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    template = f"htmx/treasurer/{module_name}.html"
    return render(request, template, context)
