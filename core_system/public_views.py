from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO

from bs4 import BeautifulSoup
from django.db.utils import ProgrammingError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

from core_system.auth_utils import sha256_hex
from core_system.constants.policy_constants import POLICY, _get_setting_override
from core_system.constants.status_constants import RegistrationStatus
from core_system.models import BylawsFile, MemberRegistrationRequest, Member, OfficerUser
from core_system.shared_view_utils import _link_proof_to_record


_POLICY_LABELS = [
    ("membership_fee", "Membership Fee"),
    ("monthly_dues", "Monthly Dues"),
    ("accidental_sickness_aid_threshold", "Accidental/Sickness Aid Threshold"),
    ("accidental_sickness_aid_benefit", "Accidental/Sickness Aid Benefit"),
    ("death_aid_member", "Death Aid — Member"),
    ("death_aid_spouse", "Death Aid — Spouse"),
    ("death_aid_parent_child", "Death Aid — Parent/Child"),
    ("death_aid_full_blood_sibling", "Death Aid — Full-Blood Sibling"),
]


@require_GET
def public_bylaws(request: HttpRequest):
    """Public endpoint returning policy constants and uploaded bylaws documents.

    No authentication required — used by the landing page to render the
    Bylaws / Policy section.
    """

    constants = []
    for key, label in _POLICY_LABELS:
        raw = _get_setting_override(key)
        if raw is not None:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value = getattr(POLICY, key)
        else:
            value = getattr(POLICY, key)
        constants.append({
            "key": key,
            "label": label,
            "value": float(value),
        })

    files = BylawsFile.objects.filter(
        verification_status="Active",
    ).order_by("-uploaded_at")

    file_list = []
    for f in files:
        file_list.append({
            "document_id": f.bylaws_file_id,
            "file_name": f.file_name,
            "file_type": f.file_type or "application/octet-stream",
            "uploaded_at": f.uploaded_at.strftime("%Y-%m-%d") if f.uploaded_at else None,
        })

    return JsonResponse({
        "ok": True,
        "generated_at": timezone.now().isoformat(),
        "constants": constants,
        "files": file_list,
    })


@require_GET
def public_register(request: HttpRequest):
    """Render the public membership registration request form."""
    membership_fee_amount = _get_setting_override("membership_fee")
    if membership_fee_amount is None:
        from core_system.constants.policy_constants import POLICY
        membership_fee_amount = getattr(POLICY, "membership_fee")
    return render(request, "website/public_register.html", {
        "membership_fee_amount": float(membership_fee_amount),
    })


@require_GET
def public_registration_field_availability(request: HttpRequest):
    """Return whether a username or email is already taken."""
    field = (request.GET.get("field") or "").strip().lower()
    value = (request.GET.get("value") or "").strip()
    if field not in {"username", "email"} or not value:
        return JsonResponse({"ok": False, "error": "Invalid validation request."}, status=400)

    try:
        if field == "username":
            taken = (
                Member.objects.filter(employee_id__iexact=value).exists()
                or MemberRegistrationRequest.objects.filter(employee_id__iexact=value).exclude(status=RegistrationStatus.REJECTED).exists()
            )
        else:
            taken = (
                Member.objects.filter(email__iexact=value).exists()
                or MemberRegistrationRequest.objects.filter(email__iexact=value).exclude(status=RegistrationStatus.REJECTED).exists()
            )
    except ProgrammingError:
        if field == "username":
            taken = Member.objects.filter(employee_id__iexact=value).exists()
        else:
            taken = Member.objects.filter(email__iexact=value).exists()

    return JsonResponse({"ok": True, "field": field, "value": value, "available": not taken})


@require_POST
def public_submit_registration_request(request: HttpRequest):
    """Accept a public member registration request with proof upload."""
    field_labels = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "username": "Username",
        "email": "Email Address",
        "department": "Department",
        "payment_method": "Payment Method",
        "amount": "Amount Paid",
        "password": "Password",
        "confirm_password": "Confirm Password",
    }

    for field, label in field_labels.items():
        if not request.POST.get(field, "").strip():
            return JsonResponse({"ok": False, "error": f"{label} is required."}, status=400)

    first_name = request.POST.get("first_name", "").strip()
    middle_initial = request.POST.get("middle_initial", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    department = request.POST.get("department", "").strip()
    position = request.POST.get("position", "").strip()
    membership_category = request.POST.get("membership_category", "Permanent").strip() or "Permanent"
    payment_method = request.POST.get("payment_method", "").strip()
    payment_date_raw = request.POST.get("payment_date", "").strip()
    amount_raw = request.POST.get("amount", "").strip()
    password = request.POST.get("password", "")
    confirm_password = request.POST.get("confirm_password", "")

    full_name = f"{first_name}{' ' + middle_initial if middle_initial else ''} {last_name}".strip()

    if password != confirm_password:
        return JsonResponse({"ok": False, "error": "Passwords do not match."}, status=400)

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return JsonResponse({"ok": False, "error": "Please enter a valid email address, e.g. user@gmail.com."}, status=400)

    if len(password) < 8:
        return JsonResponse({"ok": False, "error": "Password must be at least 8 characters."}, status=400)
    if not re.search(r"[a-z]", password):
        return JsonResponse({"ok": False, "error": "Password must include a lowercase letter."}, status=400)
    if not re.search(r"[A-Z]", password):
        return JsonResponse({"ok": False, "error": "Password must include an uppercase letter."}, status=400)
    if not re.search(r"\d", password):
        return JsonResponse({"ok": False, "error": "Password must include a number."}, status=400)
    if not re.search(r"[^A-Za-z0-9]", password):
        return JsonResponse({"ok": False, "error": "Password must include a special character."}, status=400)

    # Prevent duplicate member username/email or pending requests for same username/email
    try:
        if Member.objects.filter(employee_id__iexact=username).exists():
            return JsonResponse({"ok": False, "error": "A member with this username already exists."}, status=409)
        if MemberRegistrationRequest.objects.filter(employee_id__iexact=username).exclude(status=RegistrationStatus.REJECTED).exists():
            return JsonResponse({"ok": False, "error": "A pending registration request already exists for this username."}, status=409)
        if Member.objects.filter(email__iexact=email).exists():
            return JsonResponse({"ok": False, "error": "A member with this email already exists."}, status=409)
        if MemberRegistrationRequest.objects.filter(email__iexact=email).exclude(status=RegistrationStatus.REJECTED).exists():
            return JsonResponse({"ok": False, "error": "A pending registration request already exists for this email."}, status=409)
    except ProgrammingError:
        logger.exception("Registration check failed because MemberRegistrationRequest table is unavailable")
        return JsonResponse({"ok": False, "error": "Membership registration is temporarily unavailable. Please try again later."}, status=503)

    try:
        amount_value = float(amount_raw)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Amount must be a valid number."}, status=400)

    payment_date = None
    if payment_date_raw:
        try:
            payment_date = timezone.datetime.fromisoformat(payment_date_raw).date()
        except ValueError:
            return JsonResponse({"ok": False, "error": "Payment Date must be valid."}, status=400)

    receipt_number_value = f"REG-{timezone.now().strftime('%Y%m%d%H%M%S')}-{username}" if username else f"REG-{timezone.now().strftime('%Y%m%d%H%M%S')}"

    try:
        request_row = MemberRegistrationRequest.objects.create(
            full_name=full_name,
            employee_id=username,
            email=email or None,
            department=department or None,
            position=position or None,
            membership_category=membership_category,
            payment_method=payment_method,
            amount=amount_value,
            receipt_number=receipt_number_value,
            payment_date=payment_date,
            password_hash=sha256_hex(password),
            status=RegistrationStatus.PENDING_TREASURER_REVIEW,
            submitted_by_ip=request.META.get("REMOTE_ADDR"),
            submitted_by_user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
    except ProgrammingError:
        logger.exception("Failed to create MemberRegistrationRequest because table is unavailable")
        return JsonResponse({"ok": False, "error": "Membership registration is temporarily unavailable. Please try again later."}, status=503)

    uploaded_file = request.FILES.get("proof_file")
    if uploaded_file and uploaded_file.size > 0:
        try:
            _link_proof_to_record(uploaded_file, request_row, None)
        except Exception:
            logger.exception("Failed to attach supporting proof for registration request %s", request_row.request_id_PK)

    return JsonResponse({"ok": True, "request_id": request_row.request_id_PK})


@require_GET
def public_bylaws_render(request: HttpRequest, document_id: int):
    """Render a bylaws document to HTML for in-browser preview."""
    doc = get_object_or_404(
        BylawsFile,
        pk=document_id,
        verification_status="Active",
    )

    file_type = (doc.file_type or "").lower()
    file_name = doc.file_name or ""

    try:
        if file_name.lower().endswith(".docx") or "wordprocessingml" in file_type:
            html = _render_docx_to_html(doc.file_data)
        elif file_name.lower().endswith(".txt") or file_type == "text/plain":
            text = doc.file_data.decode("utf-8", errors="replace")
            html = "<pre>" + escapeHtml(text) + "</pre>"
        elif file_name.lower().endswith(".pdf") or file_type == "application/pdf":
            html = (
                "<p><strong>PDF Preview</strong></p>"
                "<p>This is a PDF document. Use the <strong>Download</strong> button above to view it, "
                "or open it in a new tab.</p>"
            )
        else:
            html = "<p>Preview not available for this file type. Use the <strong>Download</strong> button above.</p>"
    except Exception as e:
        return JsonResponse({
            "ok": False,
            "error": "This document could not be previewed in-browser (" + str(e) + "). Please use the Download button.",
        }, status=500)

    return JsonResponse({"ok": True, "html": html, "file_name": doc.file_name})


@require_GET
def public_bylaws_file(request: HttpRequest, document_id: int):
    """Public file download for an Active bylaws document. No login required."""
    doc = get_object_or_404(
        BylawsFile,
        pk=document_id,
        verification_status="Active",
    )

    content_type = doc.file_type or "application/octet-stream"
    response = HttpResponse(doc.file_data, content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{doc.file_name}"'
    response["Content-Length"] = str(len(doc.file_data) if doc.file_data else 0)
    return response


def _render_docx_to_html(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        if "word/document.xml" not in names:
            raise ValueError("word/document.xml not found in DOCX archive")
        xml = zf.read("word/document.xml")

    soup = BeautifulSoup(xml, "xml")
    body = soup.find("w:document")
    if body is None:
        return "<p>Empty document.</p>"

    body = body.find("w:body")
    if body is None:
        return "<p>Empty document body.</p>"

    parts = []
    for child in body.find_all(recursive=False):
        tag = child.name
        if tag == "w:p":
            parts.append(_docx_paragraph_to_html(child))
        elif tag == "w:tbl":
            parts.append(_docx_table_to_html(child))
        elif tag == "w:sectPr":
            pass

    html = "\n".join(parts)
    return html if html else "<p>No readable content found.</p>"


def _docx_paragraph_to_html(para):
    pPr = para.find("w:pPr")
    style = ""
    if pPr is not None:
        pStyle = pPr.find("w:pStyle")
        if pStyle is not None and pStyle.get("w:val"):
            style = (pStyle.get("w:val") or "").lower()

    text_parts = []
    is_bold = False
    is_italic = False
    is_underline = False

    for r in para.find_all("w:r", recursive=False):
        rPr = r.find("w:rPr")
        if rPr is not None:
            b = rPr.find("w:b")
            if b is not None:
                is_bold = True
            i = rPr.find("w:i")
            if i is not None:
                is_italic = True
            u = rPr.find("w:u")
            if u is not None:
                is_underline = True

        t = r.find("w:t")
        if t is not None and t.string:
            text = t.string
            if is_bold:
                text = "<strong>" + escapeHtml(text) + "</strong>"
            elif is_italic:
                text = "<em>" + escapeHtml(text) + "</em>"
            elif is_underline:
                text = "<u>" + escapeHtml(text) + "</u>"
            else:
                text = escapeHtml(text)
            text_parts.append(text)

        br = r.find("w:br")
        if br is not None:
            text_parts.append("<br/>")

    text = "".join(text_parts) or "&nbsp;"

    if "heading" in style or "title" in style:
        level = re.search(r"(\d+)", style)
        level = level.group(1) if level else "1"
        return "<h" + level + ">" + text + "</h" + level + ">"
    if style == "listparagraph" or para.find("w:numPr") is not None:
        return "<li>" + text + "</li>"
    return "<p>" + text + "</p>"


def _docx_table_to_html(tbl):
    rows = []
    for tr in tbl.find_all("w:tr"):
        cells = []
        for tc in tr.find_all("w:tc"):
            cell_texts = []
            for p in tc.find_all("w:p"):
                cell_texts.append(_docx_paragraph_to_html(p))
            cells.append("".join(cell_texts))
        rows.append("<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def escapeHtml(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
