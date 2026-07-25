(function () {
  "use strict";

  const CSRF_HEADER_NAME = "X-CSRFToken";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function showToast(message, isError = false) {
    const host = document.getElementById("toastContainer");
    if (!host) {
      alert(message);
      return;
    }
    const toast = document.createElement("div");
    toast.className = `custom-toast ${isError ? "toast-error" : ""}`;
    toast.innerHTML = `<p style="font-size:0.85rem;font-weight:500;margin:0;">${message}</p>`;
    host.appendChild(toast);
    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function formatMoneyPHP(num) {
    const n = typeof num === "number" ? num : parseFloat(num || "0");
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
    }).format(n);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getPaymentSourceLabel(p) {
    return (
      p.source_label ||
      (p.type === "OTC Fee Payment" ? "Membership Fee" : "Monthly Dues")
    );
  }

  function getPaymentTypeLabel(p) {
    return (
      p.payment_type ||
      (p.type === "OTC Fee Payment" ? "OTC Payment" : "OTC Payment")
    );
  }

  /* === EDIT: Map status text to badge CSS class === */
  function getStatusBadgeClass(statusText) {
    const text = (statusText || "").toLowerCase();
    if (text.indexOf("medical") !== -1) return "badge-medical-aid";
    if (text.indexOf("death") !== -1) return "badge-death-aid";
    if (text.indexOf("salary deduction") !== -1) return "badge-monthly-dues-salary";
    if (text.indexOf("otc") !== -1 || text.indexOf("monthly dues") !== -1) return "badge-monthly-dues-otc";
    if (text.indexOf("membership") !== -1) return "badge-membership-fee";
    return "badge-zero";
  }
  /* === END EDIT === */

  const PAYMENT_VERIFICATION_FIELDS = {
    membership_fee: [
      { key: "amount", label: "Actual amount paid" },
      { key: "ref", label: "Official receipt / ref code" },
      { key: "month", label: "Deduction month / Covered Period" },
      { key: "date", label: "Payment date" },
      { key: "proof_status", label: "Uploaded proof" },
      { key: "method", label: "Payment method" },
      { key: "encoded_by", label: "Encoded by" },
    ],
    monthly_dues: [
      { key: "amount", label: "Actual amount paid" },
      { key: "ref", label: "Official receipt / ref code" },
      { key: "month", label: "Deduction month / Covered Period" },
      { key: "date", label: "Payment date" },
      { key: "proof_status", label: "Uploaded proof" },
      { key: "method", label: "Payment method" },
      { key: "encoded_by", label: "Encoded by" },
    ],
  };

  const MEMBERSHIP_FEE_VERIFICATION_FIELDS = [
    { key: "amount", label: "Actual amount paid" },
    { key: "ref", label: "Official receipt / ref code" },
    { key: "payment_date", label: "Payment date" },
    { key: "proof_status", label: "Uploaded proof" },
    { key: "payment_status", label: "Payment method" },
    { key: "encoded_by", label: "Encoded by" },
  ];

  const AID_VERIFICATION_FIELDS = {
    medical_aid: [
      { key: "member_name", label: "Member Name" },
      { key: "claim_amount", label: "Claim Amount" },
      { key: "documents", label: "Supporting Documents" },
      { key: "supporting_evidence", label: "Supporting Evidence" },
      { key: "hospital_details", label: "Hospital Details" },
    ],
    death_aid: [
      { key: "member_name", label: "Member Name" },
      { key: "claim_amount", label: "Claim Amount" },
      { key: "documents", label: "Supporting Documents" },
      { key: "supporting_evidence", label: "Supporting Evidence" },
      { key: "deceased_details", label: "Deceased Details" },
    ],
  };

  function getFieldValue(item, fieldKey) {
    if (fieldKey === "proof_status") {
      return "Review evidence viewer above";
    }
    if (fieldKey.startsWith("member.")) {
      const subKey = fieldKey.slice(7);
      const member = item.member || {};
      return member[subKey] || "";
    }
    return item[fieldKey] || "";
  }

  function renderPaymentFieldCheckboxes(item) {
    const container = getEl("pAuditFieldCheckboxes");
    if (!container) return;

    const source = item.source || (item.type === "OTC Fee Payment" ? "membership_fee" : "monthly_dues");
    const fields = PAYMENT_VERIFICATION_FIELDS[source] || PAYMENT_VERIFICATION_FIELDS.membership_fee;

    container.innerHTML = "";
    fields.forEach(function (f) {
      const value = getFieldValue(item, f.key);
      const uid = "chk_p_" + f.key.replace(/\./g, "_");
      const wrapper = document.createElement("div");
      wrapper.style.cssText = "border:1px solid #dfe9df;border-radius:10px;margin-bottom:8px;background:#fff;overflow:hidden;";
      wrapper.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;">' +
        '<input type="checkbox" id="' +
        uid +
        '" data-field="' +
        f.key +
        '" style="flex-shrink:0;width:16px;height:16px;">' +
        '<label for="' +
        uid +
        '" style="font-weight:600;font-size:0.82rem;color:#1b5e20;margin:0;cursor:pointer;flex:1;">' +
        escapeHtml(f.label) +
        '</label>' +
        "</div>" +
        '<div class="chk-p-detail" style="display:none;padding:0 12px 12px 36px;">' +
        '<div style="font-size:0.78rem;color:#757575;margin-bottom:6px;line-height:1.3;">' +
        escapeHtml(value) +
        '</div>' +
        '<input type="text" data-remark-for="' +
        f.key +
        '" placeholder="Describe the issue..." style="width:100%;padding:6px 10px;border-radius:8px;border:1px solid #cfdccc;font-size:0.8rem;font-family:inherit;box-sizing:border-box;">' +
        "</div>";
      const chk = wrapper.querySelector('input[type="checkbox"]');
      const detail = wrapper.querySelector(".chk-p-detail");
      chk.addEventListener("change", function () {
        detail.style.display = chk.checked ? "block" : "none";
      });
      container.appendChild(wrapper);
    });
  }

  function renderAidFieldCheckboxes(item) {
    const container = getEl("aAuditFieldCheckboxes");
    if (!container) return;

    const aidType = item.aid_type || (item.type === "Medical Aid Request" ? "medical_aid" : "death_aid");
    const fields = AID_VERIFICATION_FIELDS[aidType] || AID_VERIFICATION_FIELDS.medical_aid;

    container.innerHTML = "";
    fields.forEach(function (f) {
      const value = getFieldValue(item, f.key);
      const uid = "chk_a_" + f.key.replace(/\./g, "_");
      const wrapper = document.createElement("div");
      wrapper.style.cssText = "border:1px solid #dfe9df;border-radius:10px;margin-bottom:8px;background:#fff;overflow:hidden;";
      wrapper.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;">' +
        '<input type="checkbox" id="' +
        uid +
        '" data-field="' +
        f.key +
        '" style="flex-shrink:0;width:16px;height:16px;">' +
        '<label for="' +
        uid +
        '" style="font-weight:600;font-size:0.82rem;color:#1b5e20;margin:0;cursor:pointer;flex:1;">' +
        escapeHtml(f.label) +
        '</label>' +
        "</div>" +
        '<div class="chk-a-detail" style="display:none;padding:0 12px 12px 36px;">' +
        '<div style="font-size:0.78rem;color:#757575;margin-bottom:6px;line-height:1.3;">' +
        escapeHtml(value) +
        '</div>' +
        '<input type="text" data-remark-for="' +
        f.key +
        '" placeholder="Describe the issue..." style="width:100%;padding:6px 10px;border-radius:8px;border:1px solid #cfdccc;font-size:0.8rem;font-family:inherit;box-sizing:border-box;">' +
        "</div>";
      const chk = wrapper.querySelector('input[type="checkbox"]');
      const detail = wrapper.querySelector(".chk-a-detail");
      chk.addEventListener("change", function () {
        detail.style.display = chk.checked ? "block" : "none";
      });
      container.appendChild(wrapper);
    });
  }

  function renderMembershipFeeFieldCheckboxes(item) {
    const container = getEl("mfAuditFieldCheckboxes");
    if (!container) return;

    container.innerHTML = "";
    MEMBERSHIP_FEE_VERIFICATION_FIELDS.forEach(function (f) {
      const value = getFieldValue(item, f.key);
      const uid = "chk_mf_" + f.key.replace(/\./g, "_");
      const wrapper = document.createElement("div");
      wrapper.style.cssText = "border:1px solid #dfe9df;border-radius:10px;margin-bottom:8px;background:#fff;overflow:hidden;";
      wrapper.innerHTML =
        '<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;">' +
        '<input type="checkbox" id="' +
        uid +
        '" data-field="' +
        f.key +
        '" style="flex-shrink:0;width:16px;height:16px;">' +
        '<label for="' +
        uid +
        '" style="font-weight:600;font-size:0.82rem;color:#1b5e20;margin:0;cursor:pointer;flex:1;">' +
        escapeHtml(f.label) +
        '</label>' +
        "</div>" +
        '<div class="chk-mf-detail" style="display:none;padding:0 12px 12px 36px;">' +
        '<div style="font-size:0.78rem;color:#757575;margin-bottom:6px;line-height:1.3;">' +
        escapeHtml(value) +
        '</div>' +
        '<input type="text" data-remark-for="' +
        f.key +
        '" placeholder="Describe the issue..." style="width:100%;padding:6px 10px;border-radius:8px;border:1px solid #cfdccc;font-size:0.8rem;font-family:inherit;box-sizing:border-box;">' +
        "</div>";
      const chk = wrapper.querySelector('input[type="checkbox"]');
      const detail = wrapper.querySelector(".chk-mf-detail");
      chk.addEventListener("change", function () {
        detail.style.display = chk.checked ? "block" : "none";
      });
      container.appendChild(wrapper);
    });
  }

  function buildRejectionDetailsJSON(containerId) {
    const container = getEl(containerId);
    if (!container) return null;

    const checkboxes = container.querySelectorAll('input[type="checkbox"]');
    const details = [];

    checkboxes.forEach(function (chk) {
      if (!chk.checked) return;
      const field = chk.getAttribute("data-field");
      const remarkInput = container.querySelector('input[data-remark-for="' + field + '"]');
      const remark = remarkInput ? remarkInput.value.trim() : "";
      if (!field) return;
      details.push({ field: field, remarks: remark });
    });

    if (details.length === 0) return null;
    return JSON.stringify({ rejection_details: details });
  }

  function renderPaymentTypeCell(p) {
    const sourceLabel = escapeHtml(getPaymentSourceLabel(p));
    const typeLabel = escapeHtml(getPaymentTypeLabel(p));
    return `
      <span class="${getStatusBadgeClass(sourceLabel)}" style="font-size:0.72rem;">${sourceLabel}</span>
      <br>
      <span class="${getStatusBadgeClass(typeLabel)}" style="font-size:0.72rem;margin-top:4px;">${typeLabel}</span>
    `;
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  let state = {
    pendingPayments: [],
    pendingAids: [],
    pendingMembershipFees: [],
    auditedLogs: [],
    selectedPaymentId: "",
    selectedAidId: "",
    selectedMembershipFeeId: "",
    selectedPaymentIds: new Set(),
    selectedAidIds: new Set(),
    selectedMfIds: new Set(),
  };

  async function getJSON(url) {
    const resp = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || `Request failed: ${url}`);
    }
    return data;
  }

  async function postForm(url, fd) {
    const csrf = getCSRFToken();
    const headers = csrf ? { [CSRF_HEADER_NAME]: csrf } : {};

    const resp = await fetch(url, {
      method: "POST",
      body: fd,
      headers,
      credentials: "same-origin",
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Server error while saving.");
    }
    return data;
  }

  function clearPaymentUI() {
    state.selectedPaymentId = "";

    const header = getEl("selectedPaymentHeader");
    if (header) header.innerText = "No item selected";

    const resets = [
      "pReadName",
      "pReadEmpId",
      "pReadDept",
      "pReadPos",
      "pReadContact",
      "pReadEmail",
      "pReadStatus",
      "pReadCovered",
      "pReadExpected",
      "pReadPaid",
      "pReadDate",
      "pReadMethod",
      "pReadRef",
      "pReadEncoder",
    ];
    resets.forEach((id) => {
      const el = getEl(id);
      if (el) el.innerText = "—";
    });

    const returnDetails = getEl("pAuditReturnDetails");
    if (returnDetails) returnDetails.style.display = "none";

    const pFieldContainer = getEl("pAuditFieldCheckboxes");
    if (pFieldContainer) pFieldContainer.innerHTML = "";

    if (window.renderEmptyState) {
      window.renderEmptyState();
    }

    const form = getEl("paymentVerificationForm");
    if (form) form.reset();
    const auditId = getEl("pAuditID");
    if (auditId) auditId.value = "";
    const preview = getEl("p_findings_preview");
    if (preview) preview.style.display = "none";
    const evidenceScreen = getEl("paymentEvidenceScreen");
    if (evidenceScreen) evidenceScreen.innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L6 21"/></svg>';
  }

  function clearAidUI() {
    state.selectedAidId = "";

    const header = getEl("selectedAidHeader");
    if (header) header.innerText = "No claim file selected";

    const fieldsContainer = getEl("aidInspectionFields");
    if (fieldsContainer) fieldsContainer.style.display = "none";

    if (window.renderEmptyState) {
      window.renderEmptyState("aidEvidenceScreen");
    }

    const form = getEl("aidVerificationForm");
    if (form) form.reset();
    const auditId = getEl("aAuditID");
    if (auditId) auditId.value = "";
    const preview = getEl("a_findings_preview");
    if (preview) preview.style.display = "none";

    const typeLabel = getEl("aidInspectionTypeLabel");
    if (typeLabel) typeLabel.innerText = "";

    if (window.toggleAidAuditEvidenceRequirement) {
      window.toggleAidAuditEvidenceRequirement();
    }
    const aidEvidenceScreen = getEl("aidEvidenceScreen");
      if (aidEvidenceScreen) aidEvidenceScreen.innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L6 21"/></svg>';

    const chkContainer = getEl("aAuditFieldCheckboxes");
    if (chkContainer) chkContainer.innerHTML = "";
    }

  function getCurrentOfficerId() {
    const el = document.getElementById("currentOfficerId");
    return el ? parseInt(el.textContent, 10) : null;
  }

  async function submitPayBatchVerify(result) {
    const ids = Array.from(state.selectedPaymentIds).map(Number);
    if (ids.length === 0) return;

    const items = state.pendingPayments
      .filter(p => state.selectedPaymentIds.has(String(p.id)))
      .map(p => ({ table_name: getPaymentTableName(p), record_id: p.entity_id }));

    if (items.length === 0) return;

    const label = result === "Verified" ? "Verify" : "Return";
    const swalResult = await Swal.fire({
      title: `${label} ${items.length} Payment Entr${items.length === 1 ? "y" : "ies"}?`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: `Yes, ${label.toLowerCase()}`,
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    let batchRemarks = "";
    if (result === "Returned") {
      const { value: remarks } = await Swal.fire({
        title: `Return ${items.length} entries?`,
        input: 'textarea',
        inputLabel: 'Reason for return (all selected items)',
        inputPlaceholder: 'Describe what needs to be corrected...',
        inputValidator: v => !v ? 'Reason is required.' : null,
        showCancelButton: true,
        confirmButtonText: 'Yes, return',
      });
      if (!remarks) return;
      batchRemarks = remarks;
    }

    try {
      const resp = await fetch("/api/auditor/verify-batch/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          items: items,
          result: result,
          remarks: batchRemarks,
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        showToast(data.error || "Batch operation failed.", true);
        return;
      }
      showToast(`Processed ${data.processed} entr${data.processed === 1 ? "y" : "ies"} (${data.skipped} skipped).`, false);
      clearPaySelection();
      await refreshAll();
    } catch (e) {
      showToast("Network/server error during batch operation.", true);
    }
  }

  function togglePayRowCheck(pid, checked) {
    if (checked) {
      state.selectedPaymentIds.add(String(pid));
    } else {
      state.selectedPaymentIds.delete(String(pid));
    }
    const row = document.querySelector(`#pendingPaymentsTable .pay-row-check[value="${pid}"]`)?.closest("tr");
    if (row) row.classList.toggle("selected-row", checked);
    updatePayBatchBar();
  }

  function updatePayBatchBar() {
    const bar = document.getElementById("pay-batch-bar");
    const countEl = document.getElementById("pay-selected-count");
    const count = state.selectedPaymentIds.size;
    if (!bar || !countEl) return;
    countEl.textContent = count + " selected";
    bar.style.display = count > 0 ? "flex" : "none";
  }

  function clearPaySelection() {
    state.selectedPaymentIds.clear();
    document.querySelectorAll("#pendingPaymentsTable .pay-row-check").forEach(cb => cb.checked = false);
    document.querySelectorAll("#pendingPaymentsTable tr").forEach(tr => tr.classList.remove("selected-row"));
    const selectAll = document.getElementById("pay-select-all");
    if (selectAll) selectAll.checked = false;
    updatePayBatchBar();
  }

  function getPaymentTableName(p) {
    return (p.source || "").toLowerCase() === "monthly_dues" ? "monthly_dues" : "membership_fee";
  }

  function createPaymentRow(p) {
    const tr = document.createElement("tr");
    const pid = p.id;
    if (state.selectedPaymentIds.has(String(pid))) {
      tr.classList.add("selected-row");
    }
    const currentId = getCurrentOfficerId();
    const prevReturnedByYou = p.returned_by_auditor_id_FK && currentId && Number(p.returned_by_auditor_id_FK) === currentId;
    const returnBadge = prevReturnedByYou ? ' <span style="color:#e53935;font-size:0.7rem;font-weight:600;">⚡ Previously returned by you</span>' : "";
    tr.innerHTML = `
      <td><input type="checkbox" class="pay-row-check" value="${pid}" ${state.selectedPaymentIds.has(String(pid)) ? "checked" : ""}></td>
      <td style="font-weight:600;color:#1b5e20;">${escapeHtml(p.ref || "")}</td>
      <td>${escapeHtml(p.member && p.member.member_name ? p.member.member_name : "")}${returnBadge}</td>
      <td style="font-weight:600;">${escapeHtml(formatMoneyPHP(p.amount))}</td>
      <td>${renderPaymentTypeCell(p)}</td>
      <td><button class="btn-select-glow">Select</button></td>
    `;
    const cb = tr.querySelector(".pay-row-check");
    cb.addEventListener("click", function (e) {
      e.stopPropagation();
      togglePayRowCheck(pid, this.checked);
    });
    tr.querySelector("button.btn-select-glow").addEventListener("click", function (e) {
      e.stopPropagation();
      selectPayment(pid);
    });
    tr.addEventListener("click", function (e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
      selectPayment(pid);
    });
    return tr;
  }

  function auditGetChecked(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v && v !== "__all__") vals.push(v); }
    return vals;
  }
  function auditGetAllValues(id) {
    var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v && v !== "__all__") vals.push(v); }
    return vals;
  }
  function auditToggleAll(containerId, checked) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v && v !== "__all__") cbs[i].checked = checked; }
    refreshAll();
  }
  function auditSyncAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    var allBox = cbs.length > 0 ? cbs[0] : null;
    if (!allBox) return;
    var allChecked = true;
    for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
    allBox.checked = allChecked;
  }
  window.auditToggleAll = auditToggleAll;
  window.auditSyncAll = auditSyncAll;
  window.auditGetChecked = auditGetChecked;
  window.auditGetAllValues = auditGetAllValues;

  function makeAuditToggle(cardId, fillFn, applyFn) {
    return function() {
      var card = document.getElementById(cardId);
      if (!card) return;
      var opening = card.style.display === "none";
      card.style.display = opening ? "block" : "none";
      if (opening) {
        fillFn();
        var handler = function(e) {
          if (card.contains(e.target)) return;
          document.removeEventListener("click", handler);
          card.style.display = "none";
        };
        setTimeout(function() { document.addEventListener("click", handler); }, 0);
      }
    };
  }

  window.audPayToggle = makeAuditToggle("audPayFilterCard",
    function() {
      var tc = document.getElementById("audPayTypeCheckboxes");
      if (tc) {
        tc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="__all__" checked onchange="auditToggleAll(\'audPayTypeCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="monthly_dues" checked onchange="auditSyncAll(\'audPayTypeCheckboxes\');refreshAll()"> <span>Monthly Dues</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="membership_fee" checked onchange="auditSyncAll(\'audPayTypeCheckboxes\');refreshAll()"> <span>Membership Fee</span></label>';
      }
    }, refreshAll);
  window.audAidToggle = makeAuditToggle("audAidFilterCard",
    function() {
      var tc = document.getElementById("audAidTypeCheckboxes");
      if (tc) {
        tc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="__all__" checked onchange="auditToggleAll(\'audAidTypeCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="medical" checked onchange="auditSyncAll(\'audAidTypeCheckboxes\');refreshAll()"> <span>Medical</span></label>' +
          '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="death" checked onchange="auditSyncAll(\'audAidTypeCheckboxes\');refreshAll()"> <span>Death Aid</span></label>';
      }
    }, refreshAll);
  window.audFeeToggle = makeAuditToggle("audFeeFilterCard",
    function() {
      var stats = {}, i, f, arr = state.pendingMembershipFees || [];
      for (i = 0; i < arr.length; i++) { f = arr[i]; if (f.payment_status) stats[String(f.payment_status).trim().replace(/\s+/g, " ")] = 1; }
      var sk = Object.keys(stats).sort();
      var sc = document.getElementById("audFeeStatusCheckboxes");
      if (sc) {
        sc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="__all__" checked onchange="auditToggleAll(\'audFeeStatusCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
        for (i = 0; i < sk.length; i++) sc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(sk[i]) + '" checked onchange="auditSyncAll(\'audFeeStatusCheckboxes\');refreshAll()"> <span>' + escapeHtml(sk[i]) + '</span></label>';
      }
    }, refreshAll);

  function renderPaymentsTable() {
    const tbody = document.querySelector("#pendingPaymentsTable tbody");
    if (!tbody) return;

    var checked = auditGetChecked("audPayTypeCheckboxes");
    if (checked.length === 0) { checked = auditGetAllValues("audPayTypeCheckboxes"); auditSyncAll("audPayTypeCheckboxes"); }

    var arr = state.pendingPayments || [], flt = [], i, p;
    for (i = 0; i < arr.length; i++) {
      p = arr[i];
      var raw = p.source_label
        ? (p.source_label === "Membership Fee" ? "membership_fee" : "monthly_dues")
        : (p.type === "OTC Fee Payment" ? "membership_fee" : "monthly_dues");
      if (checked.length && checked.indexOf(raw) === -1) continue;
      flt.push(p);
    }

    tbody.innerHTML = "";
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      updatePayBatchBar();
      return;
    }
    flt.forEach((p) => {
      const tr = createPaymentRow(p);
      tbody.appendChild(tr);
    });
    updatePayBatchBar();
  }

  function toggleAidRowCheck(aid, checked) {
    if (checked) {
      state.selectedAidIds.add(String(aid));
    } else {
      state.selectedAidIds.delete(String(aid));
    }
    const row = document.querySelector(`#pendingAidsTable .aid-row-check[value="${aid}"]`)?.closest("tr");
    if (row) row.classList.toggle("selected-row", checked);
    updateAidBatchBar();
  }

  function updateAidBatchBar() {
    const bar = document.getElementById("aid-batch-bar");
    const countEl = document.getElementById("aid-selected-count");
    const count = state.selectedAidIds.size;
    if (!bar || !countEl) return;
    countEl.textContent = count + " selected";
    bar.style.display = count > 0 ? "flex" : "none";
  }

  function clearAidSelection() {
    state.selectedAidIds.clear();
    document.querySelectorAll("#pendingAidsTable .aid-row-check").forEach(cb => cb.checked = false);
    document.querySelectorAll("#pendingAidsTable tr").forEach(tr => tr.classList.remove("selected-row"));
    const selectAll = document.getElementById("aid-select-all");
    if (selectAll) selectAll.checked = false;
    updateAidBatchBar();
  }

  function toggleMfRowCheck(fid, checked) {
    if (checked) {
      state.selectedMfIds.add(String(fid));
    } else {
      state.selectedMfIds.delete(String(fid));
    }
    const row = document.querySelector(`#pendingMfTable .mf-row-check[value="${fid}"]`)?.closest("tr");
    if (row) row.classList.toggle("selected-row", checked);
    updateMfBatchBar();
  }

  function updateMfBatchBar() {
    const bar = document.getElementById("mf-batch-bar");
    const countEl = document.getElementById("mf-selected-count");
    const count = state.selectedMfIds.size;
    if (!bar || !countEl) return;
    countEl.textContent = count + " selected";
    bar.style.display = count > 0 ? "flex" : "none";
  }

  function clearMfSelection() {
    state.selectedMfIds.clear();
    document.querySelectorAll("#pendingMfTable .mf-row-check").forEach(cb => cb.checked = false);
    document.querySelectorAll("#pendingMfTable tr").forEach(tr => tr.classList.remove("selected-row"));
    const selectAll = document.getElementById("mf-select-all");
    if (selectAll) selectAll.checked = false;
    updateMfBatchBar();
  }

  async function submitMfBatchVerify(result) {
    const ids = Array.from(state.selectedMfIds).map(Number);
    if (ids.length === 0) return;

    const items = state.pendingMembershipFees
      .filter(f => state.selectedMfIds.has(String(f.fee_id)))
      .map(f => ({ table_name: "membership_fee", record_id: f.fee_id }));

    if (items.length === 0) return;

    const label = result === "Verified" ? "Verify" : "Return";
    const swalResult = await Swal.fire({
      title: `${label} ${items.length} Membership Fee${items.length === 1 ? "" : "s"}?`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: `Yes, ${label.toLowerCase()}`,
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    let batchRemarks = "";
    if (result === "Returned") {
      const { value: remarks } = await Swal.fire({
        title: `Return ${items.length} entries?`,
        input: 'textarea',
        inputLabel: 'Reason for return (all selected items)',
        inputPlaceholder: 'Describe what needs to be corrected...',
        inputValidator: v => !v ? 'Reason is required.' : null,
        showCancelButton: true,
        confirmButtonText: 'Yes, return',
      });
      if (!remarks) return;
      batchRemarks = remarks;
    }

    try {
      const resp = await fetch("/api/auditor/verify-batch/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          items: items,
          result: result,
          remarks: batchRemarks,
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        showToast(data.error || "Batch operation failed.", true);
        return;
      }
      showToast(`Processed ${data.processed} entr${data.processed === 1 ? "y" : "ies"} (${data.skipped} skipped).`, false);
      clearMfSelection();
      await refreshAll();
    } catch (e) {
      showToast("Network/server error during batch operation.", true);
    }
  }

  function getAidTableName(a) {
    const t = (a.type || "").toLowerCase();
    return t.includes("medical") ? "medical_aid" : "death_aid";
  }

  async function submitAidBatchVerify(result) {
    const ids = Array.from(state.selectedAidIds).map(Number);
    if (ids.length === 0) return;

    const items = state.pendingAids
      .filter(a => state.selectedAidIds.has(String(a.id)))
      .map(a => ({ table_name: getAidTableName(a), record_id: a.entity_id }));

    if (items.length === 0) return;

    const label = result === "Verified" ? "Verify" : "Return";
    const swalResult = await Swal.fire({
      title: `${label} ${items.length} Aid Entr${items.length === 1 ? "y" : "ies"}?`,
      icon: "question",
      showCancelButton: true,
      confirmButtonText: `Yes, ${label.toLowerCase()}`,
      cancelButtonText: "Cancel",
      reverseButtons: true,
    });
    if (!swalResult.isConfirmed) return;

    let batchRemarks = "";
    if (result === "Returned") {
      const { value: remarks } = await Swal.fire({
        title: `Return ${items.length} entries?`,
        input: 'textarea',
        inputLabel: 'Reason for return (all selected items)',
        inputPlaceholder: 'Describe what needs to be corrected...',
        inputValidator: v => !v ? 'Reason is required.' : null,
        showCancelButton: true,
        confirmButtonText: 'Yes, return',
      });
      if (!remarks) return;
      batchRemarks = remarks;
    }

    try {
      const resp = await fetch("/api/auditor/verify-batch/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          items: items,
          result: result,
          remarks: batchRemarks,
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        showToast(data.error || "Batch operation failed.", true);
        return;
      }
      showToast(`Processed ${data.processed} entr${data.processed === 1 ? "y" : "ies"} (${data.skipped} skipped).`, false);
      clearAidSelection();
      await refreshAll();
    } catch (e) {
      showToast("Network/server error during batch operation.", true);
    }
  }

  function renderAidsTable() {
    const tbody = document.querySelector("#pendingAidsTable tbody");
    if (!tbody) return;

    var checked = auditGetChecked("audAidTypeCheckboxes");
    if (checked.length === 0) { checked = auditGetAllValues("audAidTypeCheckboxes"); auditSyncAll("audAidTypeCheckboxes"); }
    var arr = state.pendingAids || [], flt = [], i, a;
    for (i = 0; i < arr.length; i++) {
      a = arr[i];
      if (checked.length) {
        var tc = (a.type || "").toLowerCase();
        var match = (checked.indexOf("medical") !== -1 && tc.indexOf("medical") !== -1) ||
                    (checked.indexOf("death") !== -1 && tc.indexOf("death") !== -1);
        if (!match) continue;
      }
      flt.push(a);
    }

    tbody.innerHTML = "";
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      updateAidBatchBar();
      return;
    }
    flt.forEach((a) => {
      const aid = a.id;
      const tr = document.createElement("tr");
      if (state.selectedAidIds.has(String(aid))) {
        tr.classList.add("selected-row");
      }
      tr.innerHTML = `
        <td><input type="checkbox" class="aid-row-check" value="${aid}" ${state.selectedAidIds.has(String(aid)) ? "checked" : ""}></td>
        <td>${escapeHtml(a.member && a.member.member_name ? a.member.member_name : a.claimantName || "")}</td>
        <td><span class="${getStatusBadgeClass(a.type)}" style="font-size:0.75rem;">${escapeHtml(a.type || "")}</span></td>
        <td style="font-weight:600;">${formatMoneyPHP(a.reqAmount || a.benefit || 0)} <span style="font-size:0.7rem;color:#90a4ae;font-weight:400;">/per member</span></td>
        <td><button class="btn-select-glow">Select</button></td>
      `;
      const cb = tr.querySelector(".aid-row-check");
      cb.addEventListener("click", function (e) {
        e.stopPropagation();
        toggleAidRowCheck(aid, this.checked);
      });
      tr.querySelector("button.btn-select-glow").addEventListener("click", function (e) {
        e.stopPropagation();
        selectAid(aid);
      });
      tr.addEventListener("click", function (e) {
        if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
        selectAid(aid);
      });
      tbody.appendChild(tr);
    });
    updateAidBatchBar();
  }

  function renderMembershipFeesTable() {
    const tbody = document.querySelector("#pendingMembershipFeesTable tbody");
    if (!tbody) return;

    var stats = auditGetChecked("audFeeStatusCheckboxes");
    if (stats.length === 0) { stats = auditGetAllValues("audFeeStatusCheckboxes"); auditSyncAll("audFeeStatusCheckboxes"); }
    var arr = state.pendingMembershipFees || [], flt = [], i, fee;
    for (i = 0; i < arr.length; i++) {
      fee = arr[i];
      if (stats.length && stats.indexOf(fee.payment_status) === -1) continue;
      flt.push(fee);
    }

    tbody.innerHTML = "";
    if (flt.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#757580;padding:30px;">No records match current filters.</td></tr>';
      return;
    }
    flt.forEach((fee) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><input type="checkbox" class="mf-row-check" value="${fee.fee_id}"></td>
        <td style="font-weight:600;color:#1b5e20;">${escapeHtml(fee.ref || "")}</td>
        <td>${escapeHtml(fee.member_name || "")}</td>
        <td style="font-weight:600;">${formatMoneyPHP(fee.amount)}</td>
        <td>${escapeHtml(fee.payment_date || "")}</td>
        <td><span class="${getStatusBadgeClass(fee.payment_status)}" style="font-size:0.75rem;">${escapeHtml(fee.payment_status || "Pending")}</span></td>
        <td><button class="btn-select-glow">Select</button></td>
      `;
      tr.onclick = () => selectMembershipFee(fee.fee_id);
      tbody.appendChild(tr);
    });
  }

  function setEvidenceScreen({ badgeText, titleText, descText }) {
    const badge = getEl("paymentEvidenceBadge");
    const title = getEl("paymentEvidenceTitle");
    const desc = getEl("paymentEvidenceDesc");
    const screen = getEl("paymentEvidenceScreen");

    if (badge) badge.innerText = badgeText;
    if (title) title.innerText = titleText;
    if (desc) desc.innerText = descText;
    if (screen) screen.style.borderColor = "#fbc02d";
  }

  function selectPayment(id) {
    state.selectedPaymentId = String(id);

    const item = state.pendingPayments.find((p) => String(p.id) === String(id));
    if (!item) return;

    const header = getEl("selectedPaymentHeader");
    if (header)
      header.innerText = `Reviewing Entry: ${item.id} (${getPaymentSourceLabel(item)} · ${getPaymentTypeLabel(item)})`;

    const m = item.member || {};
    if (getEl("pReadName")) getEl("pReadName").innerText = m.member_name || "—";
    if (getEl("pReadEmpId"))
      getEl("pReadEmpId").innerText = m.employee_id || "—";
    if (getEl("pReadDept")) getEl("pReadDept").innerText = m.department || "—";
    if (getEl("pReadPos")) getEl("pReadPos").innerText = m.position || "—";
    if (getEl("pReadContact"))
      getEl("pReadContact").innerText = m.contact || "—";
    if (getEl("pReadEmail")) getEl("pReadEmail").innerText = m.email || "—";
    if (getEl("pReadStatus"))
      getEl("pReadStatus").innerText = m.membership_status || "—";

    if (getEl("pReadCovered"))
      getEl("pReadCovered").innerText = item.month || "—";
    if (getEl("pReadExpected"))
      getEl("pReadExpected").innerText = formatMoneyPHP(item.expected);
    if (getEl("pReadPaid"))
      getEl("pReadPaid").innerText = formatMoneyPHP(item.amount);
    if (getEl("pReadDate")) getEl("pReadDate").innerText = item.date || "—";
    if (getEl("pReadMethod"))
      getEl("pReadMethod").innerText = item.method || "—";
    if (getEl("pReadRef")) getEl("pReadRef").innerText = item.ref || "—";
    if (getEl("pReadEncoder"))
      getEl("pReadEncoder").innerText = item.encoded_by || "—";

    const auditId = getEl("pAuditID");
    if (auditId) auditId.value = item.id;
    const auditDate = getEl("pAuditDate");
    if (auditDate) auditDate.value = new Date().toLocaleString();

    const modelType =
      item.source ||
      (item.type === "OTC Fee Payment" ? "membership_fee" : "monthly_dues");
    if (window.fetchMediaForRecord) {
      window.fetchMediaForRecord(item.id, modelType).then((proof) => {
        if (proof) {
          window.renderMediaPreview(
            proof.fileUrl,
            proof.fileType,
            proof.fileName,
          );
        }
      });
    }

    renderPaymentFieldCheckboxes(item);
  }

  function selectAid(id) {
    state.selectedAidId = String(id);

    const item = state.pendingAids.find((a) => String(a.id) === String(id));
    if (!item) return;

    var numericId = String(item.aid_type === "medical_aid" || item.type === "Medical Aid Request" ? item.id : item.id).split("-").pop();
    if (isNaN(numericId)) numericId = String(item.id);

    const header = getEl("selectedAidHeader");
    if (header) header.innerText = `Inspecting Claim: ${item.id}`;

    if (window.renderAidInspectionFields) {
      window.renderAidInspectionFields(item, "aidEvidenceScreen");
    }

    const fieldsContainer = getEl("aidInspectionFields");
    if (fieldsContainer) fieldsContainer.style.display = "block";

    const auditId = getEl("aAuditID");
    if (auditId) auditId.value = item.id;
    const auditDate = getEl("aAuditDate");
    if (auditDate) auditDate.value = new Date().toLocaleString();

    const aidType = item.aid_type ||
      (item.type === "Medical Aid Request" ? "medical_aid" : "death_aid");

    if (window.fetchMediaForRecord) {
      window.fetchMediaForRecord(numericId, aidType, "aidEvidenceScreen").then((proof) => {
        if (proof && window.renderMediaPreview) {
          window.renderMediaPreview(proof.fileUrl, proof.fileType, proof.fileName, "aidEvidenceScreen");
        }
      });
    }

    if (window.toggleAidAuditEvidenceRequirement) {
      window.toggleAidAuditEvidenceRequirement();
    }

    renderAidFieldCheckboxes(item);
  }

  function clearMembershipFeeUI() {
    state.selectedMembershipFeeId = "";

    const header = getEl("selectedMembershipFeeHeader");
    if (header) header.innerText = "No fee submission selected";

    const resets = [
      "mfReadName",
      "mfReadEmpId",
      "mfReadDept",
      "mfReadPos",
      "mfReadContact",
      "mfReadEmail",
      "mfReadStatus",
      "mfReadRef",
      "mfReadAmount",
      "mfReadDate",
      "mfReadStatusDetail",
      "mfReadDeposit",
      "mfReadEncoder",
    ];
    resets.forEach((id) => {
      const el = getEl(id);
      if (el) el.innerText = "—";
    });

    const returnDetails = getEl("mfAuditReturnDetails");
    if (returnDetails) returnDetails.style.display = "none";

    const mfFieldContainer = getEl("mfAuditFieldCheckboxes");
    if (mfFieldContainer) mfFieldContainer.innerHTML = "";

    if (window.renderEmptyState) {
      window.renderEmptyState("membershipFeeEvidenceScreen");
    }

    const form = getEl("membershipFeeVerificationForm");
    if (form) form.reset();
    const auditId = getEl("mfAuditID");
    if (auditId) auditId.value = "";
    const preview = getEl("mf_findings_preview");
    if (preview) preview.style.display = "none";
    const mfEvidenceScreen = getEl("membershipFeeEvidenceScreen");
    if (mfEvidenceScreen) mfEvidenceScreen.innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L6 21"/></svg>';
  }

  function selectMembershipFee(id) {
    state.selectedMembershipFeeId = String(id);

    const item = state.pendingMembershipFees.find(
      (f) => String(f.fee_id) === String(id),
    );
    if (!item) return;

    const header = getEl("selectedMembershipFeeHeader");
    if (header) header.innerText = `Inspecting Fee: ${item.ref || item.fee_id}`;

    const m = item.member || {};
    if (getEl("mfReadName"))
      getEl("mfReadName").innerText = item.member_name || m.member_name || "—";
    if (getEl("mfReadEmpId"))
      getEl("mfReadEmpId").innerText = m.employee_id || "—";
    if (getEl("mfReadDept"))
      getEl("mfReadDept").innerText = m.department || "—";
    if (getEl("mfReadPos")) getEl("mfReadPos").innerText = m.position || "—";
    if (getEl("mfReadContact"))
      getEl("mfReadContact").innerText = m.contact || "—";
    if (getEl("mfReadEmail")) getEl("mfReadEmail").innerText = m.email || "—";
    if (getEl("mfReadStatus"))
      getEl("mfReadStatus").innerText = m.membership_status || "—";

    if (getEl("mfReadRef")) getEl("mfReadRef").innerText = item.ref || "—";
    if (getEl("mfReadAmount"))
      getEl("mfReadAmount").innerText = formatMoneyPHP(item.amount);
    if (getEl("mfReadDate"))
      getEl("mfReadDate").innerText = item.payment_date || "—";
    if (getEl("mfReadStatusDetail"))
      getEl("mfReadStatusDetail").innerText = item.payment_status || "—";
    if (getEl("mfReadDeposit"))
      getEl("mfReadDeposit").innerText = item.deposit_reference || "—";
    if (getEl("mfReadEncoder"))
      getEl("mfReadEncoder").innerText = item.encoded_by || "—";

    const auditId = getEl("mfAuditID");
    if (auditId) auditId.value = item.fee_id;
    const auditDate = getEl("mfAuditDate");
    if (auditDate) auditDate.value = new Date().toLocaleString();

    if (window.fetchMediaForRecord) {
      window
        .fetchMediaForRecord(
          item.fee_id,
          "membership_fee",
          "membershipFeeEvidenceScreen",
        )
        .then((proof) => {
          if (proof) {
            window.renderMediaPreview(
              proof.fileUrl,
              proof.fileType,
              proof.fileName,
              "membershipFeeEvidenceScreen",
            );
          }
        });
    }
  }

  function closeMembershipFeeAudit() {
    clearMembershipFeeUI();
  }

  async function refreshAll() {
    state.pendingPayments = [];
    state.pendingAids = [];
    state.pendingMembershipFees = [];

    try {
      const payments = await getJSON("/api/auditor/pending-payments/list/");
      state.pendingPayments = payments.payments || [];
    } catch (e) {
      showToast(e.message || "Failed loading pending payments.", true);
    }

    try {
      const aids = await getJSON("/api/auditor/pending-aids/list/");
      state.pendingAids = aids.aids || [];
    } catch (e) {
      showToast(e.message || "Failed loading pending aids.", true);
    }

    try {
      const fees = await getJSON("/api/auditor/pending-membership-fees/list/");
      state.pendingMembershipFees = fees.fees || [];
    } catch (e) {
      showToast(e.message || "Failed loading pending membership fees.", true);
    }

    renderPaymentsTable();
    renderAidsTable();
    renderMembershipFeesTable();
    loadAuditedLogs();

    const totalPending = state.pendingPayments.length + state.pendingAids.length;
    const dot = getEl("audit-folder-dot");
    if (dot) {
      dot.textContent = totalPending;
      dot.classList.toggle("show", totalPending > 0);
    }

    const pDot = getEl("payments-audit-dot");
    if (pDot) {
      pDot.textContent = state.pendingPayments.length;
      pDot.classList.toggle("show", state.pendingPayments.length > 0);
    }

    const aDot = getEl("aid-audit-dot");
    if (aDot) {
      aDot.textContent = state.pendingAids.length;
      aDot.classList.toggle("show", state.pendingAids.length > 0);
    }
  }

  /* === AUDITED LOGS === */
  state.auditedLogs = [];

  async function loadAuditedLogs() {
    try {
      const data = await getJSON("/api/auditor/audited-logs/");
      state.auditedLogs = data.logs || [];
    } catch (e) {
      state.auditedLogs = [];
    }
    applyAuditLogFilters();
  }

  function applyAuditLogFilters() {
    const searchVal = (getEl("auditLogSearch")?.value || "").toLowerCase().trim();
    const resultVal = (getEl("auditLogResultFilter")?.value || "").trim();
    const dateFrom = getEl("auditLogDateFrom")?.value || "";
    const dateTo = getEl("auditLogDateTo")?.value || "";

    var filtered = state.auditedLogs.filter(function (log) {
      if (searchVal && !log.member_name.toLowerCase().includes(searchVal)) return false;
      if (resultVal && (log.result || "").toLowerCase().indexOf(resultVal.toLowerCase()) === -1) return false;
      if (dateFrom && log.verified_at && log.verified_at.slice(0, 10) < dateFrom) return false;
      if (dateTo && log.verified_at && log.verified_at.slice(0, 10) > dateTo) return false;
      return true;
    });

    renderAuditedLogs(filtered);
  }

  function renderAuditedLogs(logs) {
    var tbody = document.querySelector("#auditedLogsTable tbody");
    if (!tbody) return;

      if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#757575;padding:24px;">No audited log entries found.</td></tr>';
      return;
    }

    var html = "";
    for (var i = 0; i < logs.length; i++) {
      var log = logs[i];
      var dateLabel = log.verified_at ? new Date(log.verified_at).toLocaleString() : "—";
      var amountLabel = log.amount ? formatMoneyPHP(log.amount) : "—";
      var resultBadge = (function (s) {
        var lower = (s || "").toLowerCase();
        if (lower.indexOf("verified") !== -1 || lower.indexOf("approved") !== -1 || lower.indexOf("released") !== -1)
          return '<span style="background:rgba(27,94,32,0.1);color:#1b5e20;padding:4px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">' + escapeHtml(s) + '</span>';
        if (lower.indexOf("returned") !== -1 || lower.indexOf("rejected") !== -1)
          return '<span style="background:rgba(229,57,53,0.1);color:#e53935;padding:4px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">' + escapeHtml(s) + '</span>';
        return '<span style="background:rgba(158,158,158,0.1);color:#757575;padding:4px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">' + escapeHtml(s) + '</span>';
      })(log.result);
      var evidenceIcon = log.has_evidence
        ? '<span style="color:#1b5e20;font-size:1.1rem;cursor:pointer;" title="Evidence on file">&#128206;</span>'
        : '<span style="color:#bdbdbd;font-size:0.78rem;">None</span>';

      html += "<tr>";
      html += "<td style='white-space:nowrap;font-size:0.78rem;'>" + escapeHtml(dateLabel) + "</td>";
      html += "<td>" + escapeHtml(log.transaction_type || "") + "</td>";
      html += "<td><strong>" + escapeHtml(log.member_name || "") + "</strong></td>";
      html += "<td style='font-weight:600;'>" + amountLabel + "</td>";
      html += "<td>" + resultBadge + "</td>";
      html += "<td style='max-width:220px;font-size:0.78rem;'>" + escapeHtml(log.remarks || "") + "</td>";
      html += "<td style='font-size:0.78rem;line-height:1.6;'>";
      html += "<div><span style='color:#1b5e20;font-weight:600;'>&#10003;</span> " + escapeHtml(log.auditor_name || "") + "</div>";
      html += "<div><span style='color:#1565c0;font-weight:600;'>&#10003;</span> " + escapeHtml(log.president_name || "\u2014") + "</div>";
      html += "</td>";
      html += "<td style='text-align:center;'>" + evidenceIcon + "</td>";
      html += "</tr>";
    }
    tbody.innerHTML = html;
  }

  async function handlePaymentSubmit(e) {
    e.preventDefault();

    const auditTargetId = (getEl("pAuditID") || {}).value;
    if (!auditTargetId) {
      showToast(
        "Please select an active transaction log from the inbox first.",
        true,
      );
      return;
    }

    const result = (getEl("pAuditResult") || {}).value || "";
    const swalResult1 = await Swal.fire({
      title: `Submit audit as "${result}"?`,
      text: result === 'Returned'
        ? 'This will send the record back to the Treasurer for correction.'
        : 'This will forward the record to the President for final approval.',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Yes, submit',
      cancelButtonText: 'Cancel',
      reverseButtons: true,
    });
    if (!swalResult1.isConfirmed) return;

    if (result === "Returned") {
      const checkedBoxes = document.querySelectorAll("#pAuditFieldCheckboxes input[type='checkbox']:checked");
      if (checkedBoxes.length === 0) {
        showToast("Please check at least one field that needs correction, or add a remark.", true);
        return;
      }
      const fileInput = getEl("p_findings_file");
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        showToast("Please attach finding evidence before returning.", true);
        return;
      }
    }

    let fieldRemarks = "";
    if (result === "Returned") {
      const json = buildRejectionDetailsJSON("pAuditFieldCheckboxes");
      if (json) fieldRemarks = json;
    }

    const submitBtn = document.querySelector("#paymentVerificationForm button[type='submit']");
    if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...'; }

    const fd = new FormData();
    fd.append("pAuditID", auditTargetId);
    fd.append("pAuditRemarks", (getEl("pAuditRemarks") || {}).value || "");
    fd.append("pAuditResult", result);
    fd.append("pAuditFieldRemarks", fieldRemarks);

    const fileInput = getEl("p_findings_file");
    if (fileInput && fileInput.files && fileInput.files[0]) {
      fd.append("p_findings_file", fileInput.files[0]);
    }

    try {
      await postForm("/api/auditor/verify-payment/", fd);
      showToast("Payment audit submitted to system log.", false);
      clearPaymentUI();
      await refreshAll();
    } catch (err) {
      showToast(err.message || "Failed submitting payment audit.", true);
      if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = 'Submit Verification'; }
      const btnReturn = getEl("btnReturnPaymentForCorrection");
      if (btnReturn) { btnReturn.dataset.submitting = ""; btnReturn.disabled = false; }
    }
  }

  async function handleAidSubmit(e) {
    e.preventDefault();

    const auditTargetId = (getEl("aAuditID") || {}).value;
    if (!auditTargetId) {
      showToast(
        "Please select an active claim record from the inbox first.",
        true,
      );
      return;
    }

    const aResult = (getEl("aAuditResult") || {}).value || "";
    const swalResultA1 = await Swal.fire({
      title: `Submit audit as "${aResult}"?`,
      text: aResult === 'Returned'
        ? 'This will send the record back to the Treasurer for correction.'
        : 'This will forward the record to the President for final approval.',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Yes, submit',
      cancelButtonText: 'Cancel',
      reverseButtons: true,
    });
    if (!swalResultA1.isConfirmed) return;

    if (aResult === "Returned") {
      const checkedBoxes = document.querySelectorAll("#aAuditFieldCheckboxes input[type='checkbox']:checked");
      if (checkedBoxes.length === 0) {
        showToast("Please check at least one field that needs correction, or add a remark.", true);
        return;
      }
      const fileInput = getEl("a_findings_file");
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        showToast("Please attach finding evidence before returning.", true);
        return;
      }
    }

    let fieldRemarks = "";
    if (aResult === "Returned") {
      const json = buildRejectionDetailsJSON("aAuditFieldCheckboxes");
      if (json) fieldRemarks = json;
    }

    const submitBtn = document.querySelector("#aidVerificationForm button[type='submit']");
    if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...'; }

    const fd = new FormData();
    fd.append("aAuditID", auditTargetId);
    fd.append("aAuditRemarks", (getEl("aAuditRemarks") || {}).value || "");
    fd.append("aAuditResult", aResult);
    fd.append("aAuditFieldRemarks", fieldRemarks);

    const fileInput = getEl("a_findings_file");
    if (fileInput && fileInput.files && fileInput.files[0]) {
      fd.append("a_findings_file", fileInput.files[0]);
    }

    try {
      await postForm("/api/auditor/verify-aid/", fd);
      showToast("Aid audit submitted to system log.", false);
      clearAidUI();
      await refreshAll();
    } catch (err) {
      showToast(err.message || "Failed submitting aid audit.", true);
      if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = 'Submit Verification'; }
      const btnReturn = getEl("btnReturnAidForCorrection");
      if (btnReturn) { btnReturn.dataset.submitting = ""; btnReturn.disabled = false; }
    }
  }

  async function handleMembershipFeeSubmit(e) {
    e.preventDefault();

    const auditTargetId = (getEl("mfAuditID") || {}).value;
    if (!auditTargetId) {
      showToast(
        "Please select a membership fee record from the inbox first.",
        true,
      );
      return;
    }

    const result = (getEl("mfAuditResult") || {}).value || "";
    const swalResultMf1 = await Swal.fire({
      title: `Submit audit as "${result}"?`,
      text: result === 'Returned'
        ? 'This will send the record back to the Treasurer for correction.'
        : 'This will forward the record to the President for final approval.',
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Yes, submit',
      cancelButtonText: 'Cancel',
      reverseButtons: true,
    });
    if (!swalResultMf1.isConfirmed) return;

    if (result === "Returned") {
      const checkedBoxes = document.querySelectorAll("#mfAuditFieldCheckboxes input[type='checkbox']:checked");
      if (checkedBoxes.length === 0) {
        showToast("Please check at least one field that needs correction, or add a remark.", true);
        return;
      }
      const fileInput = getEl("mf_findings_file");
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        showToast("Please attach finding evidence before returning.", true);
        return;
      }
    }

    let fieldRemarks = "";
    if (result === "Returned") {
      const json = buildRejectionDetailsJSON("mfAuditFieldCheckboxes");
      if (json) fieldRemarks = json;
    }

    const submitBtn = document.querySelector("#membershipFeeVerificationForm button[type='submit']");
    if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...'; }

    const fd = new FormData();
    fd.append("mfAuditID", auditTargetId);
    fd.append("mfAuditRemarks", (getEl("mfAuditRemarks") || {}).value || "");
    fd.append("mfAuditResult", result);
    fd.append("mfAuditFieldRemarks", fieldRemarks);

    const fileInput = getEl("mf_findings_file");
    if (fileInput && fileInput.files && fileInput.files[0]) {
      fd.append("p_findings_file", fileInput.files[0]);
    }

    try {
      await postForm("/api/auditor/verify-membership-fee/", fd);
      showToast("Membership fee audit submitted to system log.", false);
      clearMembershipFeeUI();
      await refreshAll();
    } catch (err) {
      showToast(err.message || "Failed submitting membership fee audit.", true);
      if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = 'Submit Verification'; }
      const btnReturn = getEl("btnReturnMembershipFeeForCorrection");
      if (btnReturn) { btnReturn.dataset.submitting = ""; btnReturn.disabled = false; }
      const mfAuditBtn = getEl("btnReturnMembershipFeeAuditForCorrection");
      if (mfAuditBtn) { mfAuditBtn.dataset.submitting = ""; mfAuditBtn.disabled = false; }
    }
  }

  function bindForms() {
    window.submitPaymentVerification = handlePaymentSubmit;
    window.submitAidVerification = handleAidSubmit;
    window.submitMembershipFeeVerification = handleMembershipFeeSubmit;

    const paymentForm = getEl("paymentVerificationForm");
    if (paymentForm) {
      paymentForm.onsubmit = handlePaymentSubmit;
    }

    const aidForm = getEl("aidVerificationForm");
    if (aidForm) {
      aidForm.onsubmit = handleAidSubmit;
    }

    const membershipFeeForm = getEl("membershipFeeVerificationForm");
    if (membershipFeeForm) {
      // Avoid double-binding: setting both `onsubmit` and `addEventListener('submit')`
      // causes duplicate POSTs (and duplicate backend artifacts) on a single click.
      membershipFeeForm.onsubmit = handleMembershipFeeSubmit;
    }

    const membershipFeeAuditForm = getEl("membershipFeeAuditForm");
    if (membershipFeeAuditForm) {
      membershipFeeAuditForm.onsubmit = handleMembershipFeeSubmit;
    }
  }

  function bindCancelButtons() {
    window.clearPaymentVerificationSelection = clearPaymentUI;
    window.clearAidVerificationSelection = clearAidUI;
    window.clearMembershipFeeVerificationSelection = clearMembershipFeeUI;
  }

  function bindReturnForCorrectionButtons() {
    const paymentBtn = getEl("btnReturnPaymentForCorrection");
    if (paymentBtn) {
      paymentBtn.addEventListener("click", async () => {
        if (paymentBtn.dataset.submitting === "1") return;
        const swalRes = await Swal.fire({
          title: 'Return for Correction?',
          text: 'This will send the record back to the Treasurer and require attached evidence.',
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: 'Yes, return',
          cancelButtonText: 'Cancel',
        });
        if (!swalRes.isConfirmed) return;
        paymentBtn.dataset.submitting = "1";
        paymentBtn.disabled = true;

        const resultSelect = getEl("pAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        togglePaymentAuditEvidenceRequirement();
        const form = getEl("paymentVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }

    const aidBtn = getEl("btnReturnAidForCorrection");
    if (aidBtn) {
      aidBtn.addEventListener("click", async () => {
        if (aidBtn.dataset.submitting === "1") return;
        const swalRes = await Swal.fire({
          title: 'Return for Correction?',
          text: 'This will send the record back to the Treasurer and require attached evidence.',
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: 'Yes, return',
          cancelButtonText: 'Cancel',
        });
        if (!swalRes.isConfirmed) return;
        aidBtn.dataset.submitting = "1";
        aidBtn.disabled = true;

        const resultSelect = getEl("aAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        toggleAidAuditEvidenceRequirement();
        const form = getEl("aidVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }

    const mfBtn = getEl("btnReturnMembershipFeeForCorrection");
    if (mfBtn) {
      mfBtn.addEventListener("click", async () => {
        if (mfBtn.dataset.submitting === "1") return;
        const swalRes = await Swal.fire({
          title: 'Return for Correction?',
          text: 'This will send the record back to the Treasurer and require attached evidence.',
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: 'Yes, return',
          cancelButtonText: 'Cancel',
        });
        if (!swalRes.isConfirmed) return;
        mfBtn.dataset.submitting = "1";
        mfBtn.disabled = true;

        const resultSelect = getEl("mfAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        toggleMembershipFeeAuditEvidenceRequirement();
        const form = getEl("membershipFeeVerificationForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }

    const mfAuditBtn = getEl("btnReturnMembershipFeeAuditForCorrection");
    if (mfAuditBtn) {
      mfAuditBtn.addEventListener("click", () => {
        if (mfAuditBtn.dataset.submitting === "1") return;
        mfAuditBtn.dataset.submitting = "1";
        mfAuditBtn.disabled = true;

        const resultSelect = getEl("mfAuditResult");
        if (resultSelect) resultSelect.value = "Returned";
        const form = getEl("membershipFeeAuditForm");
        if (form) form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
    }
  }

  function setupCollapsibleSidebar() {
    const sidebar = getEl("appSidebar");
    const collapseBtn = getEl("collapseBtn");
    const chevronIcon = getEl("chevronLeftIcon");

    if (collapseBtn) {
      collapseBtn.addEventListener("click", () => {
        sidebar.classList.toggle("collapsed");
        if (sidebar.classList.contains("collapsed")) {
          chevronIcon.innerHTML = `<polyline points="9 18 15 12 9 6"></polyline>`;
          collapseBtn.setAttribute("title", "Expand Sidebar Menu");
        } else {
          chevronIcon.innerHTML = `<polyline points="15 18 9 12 15 6"></polyline>`;
          collapseBtn.setAttribute("title", "Collapse Sidebar Menu");
        }
      });
    }
  }

  function setupFolders() {
    const activeLink = document.querySelector(".menu-item.active");
    if (activeLink) {
      const parentFolder = activeLink.closest(".nested-folder");
      if (parentFolder) {
        const contents = parentFolder.querySelector(".folder-contents");
        const header = parentFolder.querySelector(".folder-header");
        if (contents) contents.classList.add("open");
        const chevron = header && header.querySelector(".chevron-icon");
        if (chevron) chevron.style.transform = "rotate(180deg)";
      }
    }
  }

  function toggleFolder(folderId, headerElement) {
    const sidebar = getEl("appSidebar");
    if (sidebar && sidebar.classList.contains("collapsed")) {
      sidebar.classList.remove("collapsed");
      const chevronLeftIcon = getEl("chevronLeftIcon");
      if (chevronLeftIcon)
        chevronLeftIcon.innerHTML = `<polyline points="15 18 9 12 15 6"></polyline>`;
    }

    const contents = document.getElementById(folderId);
    if (!contents) return;
    const isOpen = contents.classList.contains("open");

    document.querySelectorAll(".folder-contents").forEach((el) => {
      el.classList.remove("open");
      const parentHeader =
        el.parentElement && el.parentElement.querySelector(".chevron-icon");
      if (parentHeader) parentHeader.style.transform = "rotate(0deg)";
    });

    if (!isOpen) {
      contents.classList.add("open");
      const chevron =
        headerElement && headerElement.querySelector(".chevron-icon");
      if (chevron) chevron.style.transform = "rotate(180deg)";
    }
  }

  function setActiveModule(targetId) {
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach((mi) => {
      mi.classList.remove("active");
      if (mi.getAttribute("data-target") === targetId) {
        mi.classList.add("active");
      }
    });

    document.querySelectorAll(".dashboard-module").forEach((mod) => {
      mod.classList.remove("active");
      if (mod.id === targetId) {
        mod.classList.add("active");
      }
    });

    const sidebar = getEl("appSidebar");
    if (sidebar) sidebar.classList.remove("open-mobile");

    var liveTabs = ["audit-members-payments", "audit-aid-requests", "Membership-Fee-Audit"];
    if (liveTabs.indexOf(targetId) !== -1) {
      refreshAll();
    }

    const activeItem = document.querySelector(
      `.menu-item[data-target="${targetId}"]`,
    );
    if (activeItem) {
      const titleEl = activeItem.querySelector(".menu-text");
      if (titleEl) {
        const currentModuleTitle = getEl("currentModuleTitle");
        if (currentModuleTitle)
          currentModuleTitle.innerText = titleEl.innerText;
      }
    }
  }

  function initOverviewCarousel() {
    var slides = document.getElementById("ocarouselSlides");
    var dotsContainer = document.getElementById("ocarouselDots");
    var prevBtn = document.getElementById("ocarouselPrev");
    var nextBtn = document.getElementById("ocarouselNext");
    if (!slides || !dotsContainer) return;
    var total = slides.children.length;
    var current = 0;
    function render() {
      slides.style.transform = "translateX(-" + (current * 100) + "%)";
      var dots = dotsContainer.querySelectorAll(".ocarousel-dot");
      dots.forEach(function (d, i) { d.classList.toggle("active", i === current); });
    }
    function goTo(idx) {
      if (idx < 0) idx = total - 1;
      if (idx >= total) idx = 0;
      current = idx;
      render();
    }
    var icons = ["fa-money-bill-wave", "fa-file-invoice", "fa-book"];
    dotsContainer.innerHTML = "";
    for (var i = 0; i < total; i++) {
      var dot = document.createElement("button");
      dot.className = "ocarousel-dot" + (i === 0 ? " active" : "");
      dot.setAttribute("aria-label", "Slide " + (i + 1));
      dot.innerHTML = '<i class="fa-solid ' + icons[i] + '"></i>';
      (function (idx) { dot.addEventListener("click", function () { goTo(idx); }); })(i);
      dotsContainer.appendChild(dot);
    }
    if (prevBtn) prevBtn.addEventListener("click", function () { goTo(current - 1); });
    if (nextBtn) nextBtn.addEventListener("click", function () { goTo(current + 1); });

    document.querySelectorAll(".ocarousel-slide [data-nav]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = this.getAttribute("data-nav");
        if (target && typeof setActiveModule === "function") { setActiveModule(target); }
      });
    });
  }

  function setupNavigation() {
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach((item) => {
      item.addEventListener("click", () => {
        const target = item.getAttribute("data-target");
        if (!target) return;

        setActiveModule(target);

        localStorage.setItem("auditor_active_tab", target);

        const sidebar = getEl("appSidebar");
        if (sidebar) sidebar.classList.remove("open-mobile");

        const titleEl = item.querySelector(".menu-text");
        if (titleEl) {
          const currentModuleTitle = getEl("currentModuleTitle");
          if (currentModuleTitle)
            currentModuleTitle.innerText = titleEl.innerText;
        }

        var parentContents = item.closest(".folder-contents");
        if (parentContents && !parentContents.classList.contains("open")) {
          var folderHeader = parentContents.parentElement && parentContents.parentElement.querySelector(".folder-header");
          if (folderHeader) toggleFolder(parentContents.id, folderHeader);
        }
      });
    });

    const mobileToggle = getEl("mobileSidebarToggle");
    if (mobileToggle) {
      mobileToggle.addEventListener("click", () => {
        const sidebar = getEl("appSidebar");
        if (sidebar) sidebar.classList.add("open-mobile");
      });
    }
  }

  function init() {
    window.triggerFileUpload =
      window.triggerFileUpload ||
      function (id) {
        const el = getEl(id);
        if (el) el.click();
      };

    window.showAttachedPreview =
      window.showAttachedPreview ||
      function (input, labelId) {
        if (input.files && input.files.length > 0) {
          const el = getEl(labelId);
          if (el) el.style.display = "block";
        }
      };

    window.togglePaymentAuditEvidenceRequirement =
      window.togglePaymentAuditEvidenceRequirement ||
      function () {
        const select = getEl("pAuditResult");
        const evidenceGroup = getEl("evidenceGroup");
        const badge = getEl("p_findings_req_badge");
        const fileInput = getEl("p_findings_file");
        const btnReturn = getEl("btnReturnPaymentForCorrection");
        const btnVerify = getEl("btnSubmitPaymentVerification");

        if (!select || !badge || !fileInput) return;

        if (select.value === "Returned") {
          badge.innerText = "Required finding evidence";
          badge.style.background = "rgba(229,57,53,0.1)";
          badge.style.color = "#e53935";
          fileInput.setAttribute("required", "");
          if (evidenceGroup) evidenceGroup.style.display = "block";
          if (btnReturn) btnReturn.style.display = "inline-flex";
          if (btnVerify) btnVerify.style.display = "none";
          const returnDetails = getEl("pAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "block";
        } else {
          badge.innerText = "Required documentation";
          badge.style.background = "rgba(27,94,32,0.1)";
          badge.style.color = "#1b5e20";
          fileInput.removeAttribute("required");
          if (evidenceGroup) {
            evidenceGroup.style.display = "none";
            fileInput.value = "";
            const previewIndicator = getEl("p_findings_preview");
            if (previewIndicator) previewIndicator.style.display = "none";
          }
          if (btnReturn) btnReturn.style.display = "none";
          if (btnVerify) btnVerify.style.display = "inline-flex";
          const returnDetails = getEl("pAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "none";
        }
      };

    window.toggleAidAuditEvidenceRequirement =
      window.toggleAidAuditEvidenceRequirement ||
      function () {
        const select = getEl("aAuditResult");
        const evidenceGroup = getEl("aEvidenceGroup");
        const badge = getEl("a_findings_req_badge");
        const fileInput = getEl("a_findings_file");
        const btnReturn = getEl("btnReturnAidForCorrection");
        const btnSubmit = getEl("btnSubmitAidVerification");

        if (!select || !badge || !fileInput) return;

        if (select.value === "Returned") {
          badge.innerText = "Required finding evidence";
          badge.style.background = "rgba(229,57,53,0.1)";
          badge.style.color = "#e53935";
          fileInput.setAttribute("required", "");
          if (evidenceGroup) evidenceGroup.style.display = "block";
          if (btnReturn) btnReturn.style.display = "inline-flex";
          if (btnSubmit) btnSubmit.style.display = "none";
        } else {
          badge.innerText = "Required documentation";
          badge.style.background = "rgba(27,94,32,0.1)";
          badge.style.color = "#1b5e20";
          fileInput.removeAttribute("required");
          if (evidenceGroup) {
            evidenceGroup.style.display = "none";
            fileInput.value = "";
            const previewIndicator = getEl("a_findings_preview");
            if (previewIndicator) previewIndicator.style.display = "none";
          }
          if (btnReturn) btnReturn.style.display = "none";
          if (btnSubmit) btnSubmit.style.display = "inline-flex";
        }
      };

    window.toggleMembershipFeeAuditEvidenceRequirement =
      window.toggleMembershipFeeAuditEvidenceRequirement ||
      function () {
        const select = getEl("mfAuditResult");
        const evidenceGroup = getEl("mfEvidenceGroup");
        const badge = getEl("mf_findings_req_badge");
        const fileInput = getEl("mf_findings_file");
        const btnReturn = getEl("btnReturnMembershipFeeForCorrection");
        const btnSubmit = getEl("btnSubmitMembershipFeeVerification");

        if (!select || !badge || !fileInput) return;

        if (select.value === "Returned") {
          badge.innerText = "Required finding evidence";
          badge.style.background = "rgba(229,57,53,0.1)";
          badge.style.color = "#e53935";
          fileInput.setAttribute("required", "");
          if (evidenceGroup) evidenceGroup.style.display = "block";
          if (btnReturn) btnReturn.style.display = "inline-flex";
          if (btnSubmit) btnSubmit.style.display = "none";
          const returnDetails = getEl("mfAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "block";
        } else {
          badge.innerText = "Required documentation";
          badge.style.background = "rgba(27,94,32,0.1)";
          badge.style.color = "#1b5e20";
          fileInput.removeAttribute("required");
          if (evidenceGroup) {
            evidenceGroup.style.display = "none";
            fileInput.value = "";
            const previewIndicator = getEl("mf_findings_preview");
            if (previewIndicator) previewIndicator.style.display = "none";
          }
          if (btnReturn) btnReturn.style.display = "none";
          if (btnSubmit) btnSubmit.style.display = "inline-flex";
          const returnDetails = getEl("mfAuditReturnDetails");
          if (returnDetails) returnDetails.style.display = "none";
        }
      };

    bindForms();
    bindCancelButtons();
    bindReturnForCorrectionButtons();
    setupNavigation();
    initOverviewCarousel();
    setupFolders();
    setupCollapsibleSidebar();

    // Restore last selected tab (persists across refresh, cleared on logout).
    const savedTab = localStorage.getItem("auditor_active_tab");
    if (savedTab) {
      setActiveModule(savedTab);
      var savedItem = document.querySelector('.menu-item[data-target="' + savedTab + '"]');
      if (savedItem) {
        var parentContents = savedItem.closest(".folder-contents");
        if (parentContents && !parentContents.classList.contains("open")) {
          var folderHeader = parentContents.parentElement && parentContents.parentElement.querySelector(".folder-header");
          if (folderHeader) toggleFolder(parentContents.id, folderHeader);
        }
      }
    }

    clearPaymentUI();
    clearAidUI();
    clearMembershipFeeUI();

    togglePaymentAuditEvidenceRequirement();
    toggleAidAuditEvidenceRequirement();
    toggleMembershipFeeAuditEvidenceRequirement();

    const paySelectAll = document.getElementById("pay-select-all");
    if (paySelectAll) {
      paySelectAll.addEventListener("change", function () {
        const checked = this.checked;
        document.querySelectorAll("#pendingPaymentsTable .pay-row-check").forEach(cb => {
          cb.checked = checked;
          const pid = cb.value;
          if (checked) state.selectedPaymentIds.add(pid);
          else state.selectedPaymentIds.delete(pid);
          const row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updatePayBatchBar();
      });
    }
    document.getElementById("pay-batch-verify")?.addEventListener("click", function () {
      submitPayBatchVerify("Verified");
    });
    document.getElementById("pay-batch-return")?.addEventListener("click", function () {
      submitPayBatchVerify("Returned");
    });
    document.getElementById("pay-batch-clear")?.addEventListener("click", function () {
      clearPaySelection();
    });

    const aidSelectAll = document.getElementById("aid-select-all");
    if (aidSelectAll) {
      aidSelectAll.addEventListener("change", function () {
        const checked = this.checked;
        document.querySelectorAll("#pendingAidsTable .aid-row-check").forEach(cb => {
          cb.checked = checked;
          const aid = cb.value;
          if (checked) state.selectedAidIds.add(aid);
          else state.selectedAidIds.delete(aid);
          const row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updateAidBatchBar();
      });
    }
    document.getElementById("aid-batch-verify")?.addEventListener("click", function () {
      submitAidBatchVerify("Verified");
    });
    document.getElementById("aid-batch-return")?.addEventListener("click", function () {
      submitAidBatchVerify("Returned");
    });
    document.getElementById("aid-batch-clear")?.addEventListener("click", function () {
      clearAidSelection();
    });

    const mfSelectAll = document.getElementById("mf-select-all");
    if (mfSelectAll) {
      mfSelectAll.addEventListener("change", function () {
        const checked = this.checked;
        document.querySelectorAll("#pendingMfTable .mf-row-check").forEach(cb => {
          cb.checked = checked;
          const fid = cb.value;
          if (checked) state.selectedMfIds.add(fid);
          else state.selectedMfIds.delete(fid);
          const row = cb.closest("tr");
          if (row) row.classList.toggle("selected-row", checked);
        });
        updateMfBatchBar();
      });
    }
    document.getElementById("mf-batch-verify")?.addEventListener("click", function () {
      submitMfBatchVerify("Verified");
    });
    document.getElementById("mf-batch-return")?.addEventListener("click", function () {
      submitMfBatchVerify("Returned");
    });
    document.getElementById("mf-batch-clear")?.addEventListener("click", function () {
      clearMfSelection();
    });

    refreshAll();
    loadAuditedLogs();

    let logSearchDebounce;
    getEl("auditLogSearch")?.addEventListener("input", function () {
      clearTimeout(logSearchDebounce);
      logSearchDebounce = setTimeout(applyAuditLogFilters, 300);
    });
    getEl("auditLogResultFilter")?.addEventListener("change", applyAuditLogFilters);
    getEl("auditLogDateFrom")?.addEventListener("change", applyAuditLogFilters);
    getEl("auditLogDateTo")?.addEventListener("change", applyAuditLogFilters);
  }

  // Global handlers for inline onclick attributes
  window.confirmLogout = function () {
    const logoutUrl = "/logout/";
    Swal.fire({
      title: "Logout?",
      text: "Do you want to log out of the system?",
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, logout",
      cancelButtonText: "No, stay",
      reverseButtons: true,
    }).then((result) => {
      if (result.isConfirmed) {
        // Clear persisted tab on logout
        localStorage.removeItem("auditor_active_tab");
        window.location.href = logoutUrl;
      }
    });
  };

  window.triggerConfirmYes = function () {
    clearPaymentUI();
    clearAidUI();
    refreshAll();
    const modal = getEl("customConfirmModal");
    if (modal) modal.style.display = "none";
    showToast(
      "Compliance Database successfully flushed back to defaults.",
      false,
    );
  };

  window.closeConfirmModal = function () {
    const modal = getEl("customConfirmModal");
    if (modal) modal.style.display = "none";
  };

  window.showCustomModal = function (title, text) {
    const titleEl = getEl("modalAlertTitle");
    const textEl = getEl("modalAlertMessage");
    if (titleEl) titleEl.innerText = title;
    if (textEl) textEl.innerText = text;
    const modal = getEl("customAlertModal");
    if (modal) modal.style.display = "flex";
  };

  window.closeCustomModal = function () {
    const modal = getEl("customAlertModal");
    if (modal) modal.style.display = "none";
  };

  window.toggleFolder = toggleFolder;

  window.handleReportCompilerSubmit = function (e) {
    e.preventDefault();
    showToast(
      "Report compilation functionality requires backend implementation.",
      false,
    );
  };

  document.addEventListener("turbo:load", init);
})();
