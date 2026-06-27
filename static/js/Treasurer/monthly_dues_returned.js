(function () {
  "use strict";

  const MENU_TARGET_ID = "view-monthly-dues-returned";

  const FORM_ID = "monthlyDuesReturnedEditForm";
  const SELECT_RECORD_ID = "monthly_dues_returned_record_id";

  const INPUT_MONTH_COVERED = "month_covered";
  const INPUT_PAYMENT_DATE = "payment_date";
  const INPUT_AMOUNT = "amount";
  const INPUT_PAYMENT_METHOD = "payment_method";
  const INPUT_PAYMENT_STATUS = "payment_status";
  const INPUT_RECEIPT_NUMBER = "md_returned_ref";
  const INPUT_REMITTANCE_REFERENCE = "remittance_reference";
  const INPUT_DEDUCTION_BATCH_REFERENCE = "deduction_batch_reference";

  const CSRF_HEADER_NAME = "X-CSRFToken";

  let isSubmitting = false;

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function showToast(message, isError = false) {
    if (typeof window.showToast === "function") {
      window.showToast(message, isError);
      return;
    }
    alert(message);
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function extractRejectionDetails(text) {
    if (!text) return [];
    const match = text.match(/"rejection_details"\s*:\s*(\[.*?\])/s);
    if (match) {
      try {
        return JSON.parse(match[1]);
      } catch (e) {
        return [];
      }
    }
    return [];
  }

  function cleanRejectionReason(text) {
    if (!text) return "";
    const idx = text.indexOf('{"rejection_details"');
    if (idx !== -1) return text.substring(0, idx).trim();
    return text.trim();
  }

  function getRejectionDetails(record) {
    if (record.rejection_details && record.rejection_details.length > 0) {
      return record.rejection_details;
    }
    return extractRejectionDetails(record.rejection_reason);
  }

  function normalizeCoveredMonth(value) {
    const trimmed = String(value || "").trim();
    const fullMatch = trimmed.match(/^(\d{4})-(0[1-9]|1[0-2])-(\d{2})$/);
    if (fullMatch) return `${fullMatch[1]}-${fullMatch[2]}`;
    const ymMatch = trimmed.match(/^(\d{4})-(0[1-9]|1[0-2])$/);
    if (ymMatch) return `${ymMatch[1]}-${ymMatch[2]}`;
    const parsed = new Date(trimmed);
    if (!Number.isNaN(parsed.getTime())) {
      const y = parsed.getFullYear();
      const m = String(parsed.getMonth() + 1).padStart(2, "0");
      return `${y}-${m}`;
    }
    return trimmed;
  }

  async function fetchReturnedMonthlyDues() {
    const resp = await fetch("/api/treasurer/monthly-dues/returned/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data || !data.ok)
      throw new Error(
        (data && data.error) || "Failed to load returned monthly dues.",
      );
    return data.records || [];
  }

  function renderReturnedRecords(records) {
    const tbody = document.querySelector("#monthlyDuesReturnedTable tbody");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (!records || records.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align:center;color:#757575;">No returned monthly dues entries</td></tr>';
      return;
    }

    records.forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.recordId = String(r.dues_id_PK);
      tr.innerHTML = `
        <td>${escapeHtml(r.member_name || "")}<br><span style="font-size:0.75rem;color:#757575;">Code: ${r.member_id_PK || ""}</span></td>
        <td style="font-weight:600;">${escapeHtml(r.month_covered || "")}<br><span style="font-size:0.75rem;color:#757575;">Date: ${r.payment_date || ""}</span></td>
        <td style="font-weight:600;">${escapeHtml(r.amount || "0")}</td>
        <td>${escapeHtml(r.payment_status || "")}<br><span style="font-size:0.75rem;color:#757575;">${escapeHtml(r.payment_method || "")}</span></td>
        <td>${escapeHtml(r.receipt_number || r.remittance_reference || "")}</td>
        <td>${escapeHtml(cleanRejectionReason(r.rejection_reason || "")) || "—"}</td>
        <td><button type="button" class="btn-brand btn-brand-secondary" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;" onclick="window.__selectReturnedMonthlyDues('${r.dues_id_PK}')">Edit</button></td>
      `;
      tbody.appendChild(tr);
    });
  }

  function fillEditForm(record) {
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = record.dues_id_PK;

    const setVal = (id, v) => {
      const el = getEl(id);
      if (el) el.value = v ?? "";
    };

    setVal(INPUT_MONTH_COVERED, record.month_covered || "");
    setVal(INPUT_PAYMENT_DATE, record.payment_date || "");
    setVal(INPUT_AMOUNT, record.amount || "");
    setVal(INPUT_PAYMENT_METHOD, record.payment_method || "");
    setVal(INPUT_PAYMENT_STATUS, record.payment_status || "Paid");
    setVal(INPUT_RECEIPT_NUMBER, record.receipt_number || "");
    setVal(INPUT_REMITTANCE_REFERENCE, record.remittance_reference || "");
    setVal(INPUT_DEDUCTION_BATCH_REFERENCE, record.deduction_batch_reference || "");

    const rej = document.getElementById("md_rejection_reason_display");
    if (rej) rej.textContent = cleanRejectionReason(record.rejection_reason) || "No rejection reason on file.";

    const container = document.getElementById("md_rejection_details_container");
    if (container) {
      container.innerHTML = "";
      const details = getRejectionDetails(record);
      if (details.length === 0) {
        container.style.display = "none";
      } else {
        container.style.display = "block";
        details.forEach(function (d) {
          const fieldLabel = d.field || "Unknown field";
          const remark = d.remarks || "";
          const item = document.createElement("div");
          item.style.cssText = "border:1px solid #e53935;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:#fff5f5;";
          item.innerHTML =
            '<div style="font-weight:600;font-size:0.82rem;color:#e53935;margin-bottom:4px;">' +
            escapeHtml(fieldLabel) +
            "</div>" +
            (remark
              ? '<div style="font-size:0.8rem;color:#546e7a;line-height:1.4;">' +
                escapeHtml(remark) +
                "</div>"
              : "");
          container.appendChild(item);
        });
      }
    }

    const slot = document.querySelector("#monthlyDuesReturnedEditForm .photo-upload-slot");
    const existingIndicator = document.getElementById("md_returned_preview");
    if (slot && existingIndicator) {
      if (record.proof_url) {
        existingIndicator.innerHTML = `
          <img src="${escapeHtml(record.proof_url)}" style="max-height:140px;border-radius:8px;margin-top:8px;border:1px solid #cfdccc;" />
          <div style="font-size:0.8rem;color:#757575;margin-top:4px;">Existing attachment on record</div>
        `;
        existingIndicator.style.display = "block";
      } else {
        existingIndicator.innerHTML = "✓ Receipt Document Attached!";
        existingIndicator.style.display = "none";
      }
    }

    const photoInput = document.getElementById("md_returned_photo_file");
    if (photoInput) photoInput.value = "";

    const thumbnailContainer = document.getElementById("md_returned_thumbnail_container");
    const thumbnailImg = document.getElementById("md_returned_thumbnail");
    const thumbnailLink = document.getElementById("md_returned_thumbnail_link");
    if (thumbnailContainer && thumbnailImg && thumbnailLink) {
      if (record.proof_url) {
        thumbnailImg.src = record.proof_url;
        thumbnailLink.href = record.proof_url;
        thumbnailContainer.style.display = "block";
      } else {
        thumbnailContainer.style.display = "none";
        thumbnailImg.src = "";
        thumbnailLink.href = "";
      }
    }
  }

  function clearEditForm() {
    const sel = getEl(SELECT_RECORD_ID);
    if (sel) sel.value = "";
    const rej = document.getElementById("md_rejection_reason_display");
    if (rej) rej.textContent = "Select a record to view rejection reason";
    const container = document.getElementById("md_rejection_details_container");
    if (container) {
      container.innerHTML = "";
      container.style.display = "none";
    }
  }

  async function submitCorrection(e) {
    e.preventDefault();
    if (isSubmitting) return;

    const recordId = getEl(SELECT_RECORD_ID)?.value;
    if (!recordId) {
      showToast("Select a returned entry to edit.", true);
      return;
    }

    const month_covered = normalizeCoveredMonth(getEl(INPUT_MONTH_COVERED)?.value || "");
    const payment_date = getEl(INPUT_PAYMENT_DATE)?.value;
    const amount = getEl(INPUT_AMOUNT)?.value;
    const payment_method = getEl(INPUT_PAYMENT_METHOD)?.value;
    const payment_status = getEl(INPUT_PAYMENT_STATUS)?.value;
    const receipt_number = getEl(INPUT_RECEIPT_NUMBER)?.value;
    const remittance_reference = getEl(INPUT_REMITTANCE_REFERENCE)?.value || "";
    const deduction_batch_reference = getEl(INPUT_DEDUCTION_BATCH_REFERENCE)?.value || "";

    if (!payment_date) {
      showToast("Payment date is required.", true);
      return;
    }
    if (!month_covered || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month_covered)) {
      showToast("Month covered must be YYYY-MM.", true);
      return;
    }
    if (!amount) {
      showToast("Amount is required.", true);
      return;
    }
    if (!payment_method) {
      showToast("Payment method is required.", true);
      return;
    }
    if (!receipt_number) {
      showToast("Receipt/Reference number is required.", true);
      return;
    }
    if (payment_method === "Salary Deduction" && !remittance_reference) {
      showToast("Remittance reference is required for Salary Deduction.", true);
      return;
    }

    const fd = new FormData();
    fd.append("month_covered", month_covered);
    fd.append("payment_date", payment_date);
    fd.append("amount", amount);
    fd.append("payment_method", payment_method);
    fd.append("payment_status", payment_status);
    fd.append("receipt_number", receipt_number);
    fd.append("remittance_reference", remittance_reference);
    fd.append("deduction_batch_reference", deduction_batch_reference);

    const photoInput = document.getElementById("md_returned_photo_file");
    if (photoInput && photoInput.files && photoInput.files[0]) {
      fd.append("md_returned_photo_file", photoInput.files[0]);
    }

    try {
      isSubmitting = true;
      const csrf = getCSRFToken();
      const resp = await fetch(
        `/api/treasurer/resubmit/monthly_dues/${recordId}/`,
        {
          method: "POST",
          body: fd,
          headers: csrf ? { [CSRF_HEADER_NAME]: csrf } : {},
          credentials: "same-origin",
        },
      );

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        isSubmitting = false;
        showToast((data && data.error) || "Failed to submit correction.", true);
        return;
      }

      showToast("Returned monthly dues entry updated and resubmitted.");

      const records = await fetchReturnedMonthlyDues();
      window.__renderReturnedMonthlyDuesList(records);
      isSubmitting = false;
      clearEditForm();
    } catch (err) {
      isSubmitting = false;
      showToast("Network/server error while submitting correction.", true);
    }
  }

  function wireUp() {
    const form = getEl(FORM_ID);
    if (form) {
      form.addEventListener("submit", submitCorrection);
    }

    window.__selectReturnedMonthlyDues = function (duesId) {
      const rec = window.__returnedMonthlyDuesRecords?.find(
        (r) => String(r.dues_id_PK) === String(duesId),
      );
      if (!rec) return;
      fillEditForm(rec);
    };

    window.__renderReturnedMonthlyDuesList = function (records) {
      renderReturnedRecords(records);
      window.__returnedMonthlyDuesRecords = records;
    };
  }

  async function init() {
    wireUp();

    try {
      const records = await fetchReturnedMonthlyDues();
      window.__renderReturnedMonthlyDuesList(records);
    } catch (e) {
      console.error(e);
      renderReturnedRecords([]);
      window.__returnedMonthlyDuesRecords = [];
      clearEditForm();
    }
  }

  window.addEventListener("DOMContentLoaded", init);
})();
