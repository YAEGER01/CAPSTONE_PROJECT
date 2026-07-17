from __future__ import annotations

import re
import zipfile
from io import BytesIO

from bs4 import BeautifulSoup
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET

from core_system.constants.policy_constants import POLICY, _get_setting_override
from core_system.models import BylawsFile


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
