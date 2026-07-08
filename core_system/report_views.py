from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from core_system.guards import require_officer_session
from core_system.services.reporting import (
    generate_overall_report,
    generate_department_report,
    generate_contribution_report,
)


def _report_role_guard(request):
    guard = require_officer_session(request)
    if guard is not None:
        return guard
    officer_role = (request.session.get("role") or "").strip().lower()
    if officer_role in ("treasurer", "auditor", "president"):
        return None
    return None


def _download_response(wb, filename):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@require_GET
def download_overall_report(request: HttpRequest):
    guard = _report_role_guard(request)
    if guard:
        return guard

    year = request.GET.get("year")
    month = request.GET.get("month")
    if year:
        year = int(year)
    if month:
        month = int(month)

    wb = generate_overall_report(year, month)
    period = f"{year or 'current'}-{month or 'current'}"
    return _download_response(wb, f"overall_report_{period}.xlsx")


@require_GET
def download_department_report(request: HttpRequest, dept_id: int):
    guard = _report_role_guard(request)
    if guard:
        return guard

    year = request.GET.get("year")
    month = request.GET.get("month")
    if year:
        year = int(year)
    if month:
        month = int(month)

    wb = generate_department_report(dept_id, year, month)
    if wb is None:
        return HttpResponse("Department not found", status=404)

    period = f"{year or 'current'}-{month or 'current'}"
    return _download_response(wb, f"department_{dept_id}_report_{period}.xlsx")


@require_GET
def download_contribution_report(request: HttpRequest):
    guard = _report_role_guard(request)
    if guard:
        return guard

    post_id = request.GET.get("post_id")
    if post_id:
        post_id = int(post_id)

    wb = generate_contribution_report(post_id)
    return _download_response(
        wb,
        f"contribution_report_{post_id or 'all'}.xlsx",
    )
