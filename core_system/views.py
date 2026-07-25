# =========================================================================
# MIGRATION STATUS — All views moved to dedicated files:
#   - President views   → president_views.py
#   - Treasurer views   → treasurer_views.py
#   - Auditor views     → auditor_views.py
# This file now only re-exports logout_view + shared fund ledger views.
# =========================================================================
from __future__ import annotations

from typing import Any

from django.db.models import Q, Sum, Prefetch
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core_system.guards import require_officer_session
from core_system.models import (
    FundTransaction,
    Member,
    PayrollBatch,
    PayrollDeduction,
    SystemSetting,
)
from core_system.logout_view import logout_view

logout_view = logout_view


def error_page(request):
    code = request.GET.get("code", "Error")
    title = request.GET.get("title", "Something went wrong")
    message = request.GET.get("message", "An unexpected error occurred.")
    details = request.GET.get("details", "")
    icon_map = {"403": "shield-keyhole", "404": "magnifying-glass", "500": "gear"}
    icon = icon_map.get(str(code), "triangle-exclamation")
    return render(request, "errors/generic_error.html", {
        "code": code,
        "title": title,
        "message": message,
        "details": details,
        "icon": icon,
    })


@require_GET
def fund_ledger_list(request: HttpRequest):
    """Return paginated FundTransaction entries — visible to all roles."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 50))
    direction = request.GET.get("direction", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    qs = FundTransaction.objects.select_related("recorded_by_user_id_FK").all()

    if direction in ("inflow", "outflow"):
        qs = qs.filter(direction=direction)
    if date_from:
        qs = qs.filter(recorded_at__gte=date_from)
    if date_to:
        qs = qs.filter(recorded_at__lte=date_to)

    total = qs.count()
    qs = qs.order_by("-recorded_at")

    offset = (page - 1) * per_page
    entries = qs[offset:offset + per_page]

    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    total_in = float(totals["total_in"] or 0)
    total_out = float(totals["total_out"] or 0)
    balance = total_in - total_out

    items = []
    for e in entries:
        items.append({
            "id": e.transaction_id_PK,
            "direction": e.direction,
            "amount": float(e.amount),
            "source_type": e.source_type,
            "description": e.description,
            "reference_number": e.reference_number or "",
            "recorded_by": e.recorded_by_user_id_FK.full_name if e.recorded_by_user_id_FK else "",
            "recorded_at": e.recorded_at.isoformat() if e.recorded_at else "",
        })

    return JsonResponse({
        "ok": True,
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        "summary": {
            "total_in": total_in,
            "total_out": total_out,
            "balance": balance,
        },
    })


@require_GET
def fund_balance_summary(request: HttpRequest):
    """Return current fund balance + safety threshold — visible to all roles."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    balance = float(totals["total_in"] or 0) - float(totals["total_out"] or 0)

    threshold, _ = SystemSetting.objects.get_or_create(
        setting_key="safety_threshold",
        defaults={"setting_value": "20000"},
    )
    safety_threshold = float(threshold.setting_value)

    # Monthly totals
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_in = FundTransaction.objects.filter(
        direction="inflow", recorded_at__gte=month_start
    ).aggregate(total=Sum("amount"))["total"] or 0
    month_out = FundTransaction.objects.filter(
        direction="outflow", recorded_at__gte=month_start
    ).aggregate(total=Sum("amount"))["total"] or 0

    return JsonResponse({
        "ok": True,
        "balance": balance,
        "safety_threshold": safety_threshold,
        "available": balance - safety_threshold,
        "month_in": float(month_in),
        "month_out": float(month_out),
    })


@require_GET
def member_deductions_list(request: HttpRequest, member_id: int | None = None):
    """Return deduction history for a specific member — visible to all roles."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    if member_id is None:
        member_id = request.GET.get("member_id", "")
        if not member_id:
            return JsonResponse({"ok": False, "error": "member_id required."}, status=400)

    member = get_object_or_404(Member, pk=int(member_id))

    deductions = PayrollDeduction.objects.filter(
        member_id_FK=member,
        batch_id_FK__status="Approved",
    ).select_related("batch_id_FK", "aid_tracking_post_id_FK").order_by("-batch_id_FK__created_at")

    items = []
    for d in deductions:
        batch = d.batch_id_FK
        aid_ref = ""
        if d.aid_tracking_post_id_FK:
            post = d.aid_tracking_post_id_FK
            aid_ref = f"{post.aid_type}#{post.source_id}" if post.source_id else post.aid_type
        items.append({
            "date": batch.president_approved_at.isoformat() if batch.president_approved_at else "",
            "payroll_period": batch.payroll_period,
            "category": d.category,
            "amount": float(d.amount),
            "fund_impact": d.fund_impact,
            "aid_reference": aid_ref,
            "month_covered": d.month_covered or "",
            "batch_id": batch.batch_id_PK,
            "description": _build_member_deduction_desc(d, batch),
        })

    total_deducted = sum(i["amount"] for i in items)

    return JsonResponse({
        "ok": True,
        "member_id": member.member_id_PK,
        "member_name": member.full_name,
        "deductions": items,
        "total_deducted": total_deducted,
        "count": len(items),
    })


def _build_member_deduction_desc(deduction: PayrollDeduction, batch: PayrollBatch) -> str:
    label = dict(PayrollDeduction.CATEGORY_CHOICES).get(deduction.category, deduction.category)
    period = f" ({deduction.month_covered})" if deduction.month_covered else ""
    return f"{label}{period} — {batch.payroll_period}"
