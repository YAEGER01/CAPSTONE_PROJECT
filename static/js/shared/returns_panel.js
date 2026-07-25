(function () {
  "use strict";

  let state = {
    returns: [],
    filtered: [],
    selected: null,
    isSubmitting: false,
    role: "",
    activeTab: "all",
    originalFormValues: {},
  };

  const CSRF_HEADER = "X-CSRFToken";

  function el(id) { return document.getElementById(id); }

  function getCSRFToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function escapeHtml(v) {
    return String(v ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
  }

  function showToast(msg, isError) {
    const c = el("toastContainer");
    if (!c) return;
    const t = document.createElement("div");
    t.className = "custom-toast" + (isError ? " toast-error" : "");
    t.innerHTML = '<span style="font-size:1.1rem;">' + (isError ? "&#10060;" : "&#10004;") + '</span><span>' + escapeHtml(msg) + '</span>';
    c.appendChild(t);
    requestAnimationFrame(() => t.classList.add("show"));
    setTimeout(() => { t.classList.remove("show"); setTimeout(() => t.remove(), 400); }, 3500);
  }

  function getPanel() { return document.getElementById("sharedReturnsPanel"); }

  async function loadReturns() {
    const resp = await fetch("/api/shared/returns/list/", { credentials: "same-origin" });
    const data = await resp.json();
    if (!resp.ok || !data.ok) { showToast(data?.error || "Failed to load returns", true); return; }
    state.returns = data.returns || [];
    state.role = data.role || "";
    applyFilter();
  }

  function applyFilter() {
    const tab = state.activeTab;
    if (tab === "all") { state.filtered = state.returns.slice(); }
    else { state.filtered = state.returns.filter(r => r.table_name === tab); }
    renderTable();
    updateTotal();
  }

  function updateTotal() {
    const badge = el("returnsTotalBadge");
    if (!badge) return;
    const total = state.filtered.length;
    if (total === 0) { badge.style.display = "none"; return; }
    badge.style.display = "inline-flex";
    badge.textContent = total + " item" + (total !== 1 ? "s" : "");
    badge.className = "badge-zero " + (total > 5 ? "badge-red" : "badge-yellow");
  }

  function renderTable() {
    const tbody = el("returnsTableBody");
    if (!tbody) return;
    const items = state.filtered;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#757575;padding:30px;">No returned entries to display.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    items.forEach(item => {
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      tr.dataset.tvId = item.tv_id;

      const isReturned = !item.resubmitted;
      const statusLabel = isReturned ? "Returned" : "Resubmitted";
      const statusColor = isReturned ? "#e53935" : "#2e7d32";
      const statusBg = isReturned ? "#ffebee" : "#e8f5e9";

      let returnWarn = "";
      if (item.return_count > 1 && isReturned) {
        returnWarn = '<span style="display:inline-flex;align-items:center;gap:3px;margin-left:4px;padding:1px 6px;border-radius:4px;background:#fff3e0;color:#e65100;font-size:0.65rem;font-weight:700;">&#9888; ' + item.return_count + '&#215;</span>';
      }

      let actionHtml;
      if (isReturned) {
        actionHtml = '<button type="button" class="btn-brand btn-brand-secondary" style="padding:3px 8px;font-size:0.7rem;border-radius:4px;">' + (state.role === "treasurer" ? "Edit" : "View") + '</button>';
      } else {
        actionHtml = '<span style="color:#2e7d32;font-weight:600;font-size:0.75rem;">&#10004; Done</span>';
      }

      tr.innerHTML = [
        '<td><span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:4px;background:' + statusBg + ';color:' + statusColor + ';font-size:0.7rem;font-weight:600;white-space:nowrap;">',
        isReturned ? "&#9679;" : "&#9679;",
        " " + statusLabel + "</span></td>",
        '<td style="font-weight:600;">' + escapeHtml(item.entity_label) + '</td>',
        '<td>' + escapeHtml(item.member_name) + (item.member_id ? '<br><span style="font-size:0.7rem;color:#757575;">ID: ' + escapeHtml(String(item.member_id)) + '</span>' : "") + '</td>',
        '<td>' + escapeHtml(item.month_covered || "—") + '</td>',
        '<td style="font-weight:600;">' + escapeHtml(item.amount || "—") + '</td>',
        '<td style="text-align:center;">' + returnWarn + '</td>',
        '<td>' + actionHtml + '</td>',
      ].join("");
      tbody.appendChild(tr);

      if (isReturned) {
        tr.addEventListener("click", () => selectReturn(item));
      }
    });
  }

  function selectReturn(item) {
    state.selected = item;
    const panel = el("returnsDetailsPanel");
    const title = el("returnsDetailTitle");
    if (panel) panel.style.display = "block";
    if (title) title.textContent = item.entity_label + " — " + item.member_name;

    const banner = el("returnsRejectionBanner");
    if (banner) {
      if (item.returned_reason) {
        banner.style.display = "block";
        banner.style.cssText = "display:block;padding:10px 14px;border-radius:8px;margin-bottom:12px;font-size:0.85rem;background:#fff3e0;border:1px solid #ffcc02;color:#e65100;";
        let warn = item.return_count > 1 ? '&#9888; Returned ' + item.return_count + ' times. ' : "";
        banner.innerHTML = '<strong>' + warn + 'Rejection reason:</strong> ' + escapeHtml(item.returned_reason);
      } else {
        banner.style.display = "none";
      }
    }

    const fieldsContainer = el("returnsDetailFields");
    if (fieldsContainer) {
      fieldsContainer.innerHTML = "";
      if (item.returned_by) {
        fieldsContainer.innerHTML += '<div class="form-group"><label style="font-size:0.72rem;color:#757575;">Returned By</label><div style="font-weight:600;font-size:0.85rem;">' + escapeHtml(item.returned_by) + '</div></div>';
      }
      if (item.returned_at) {
        fieldsContainer.innerHTML += '<div class="form-group"><label style="font-size:0.72rem;color:#757575;">Returned At</label><div style="font-weight:600;font-size:0.85rem;">' + escapeHtml(item.returned_at) + '</div></div>';
      }
      if (item.return_count) {
        fieldsContainer.innerHTML += '<div class="form-group"><label style="font-size:0.72rem;color:#757575;">Return Count</label><div style="font-weight:600;font-size:0.85rem;color:' + (item.return_count > 1 ? "#e53935" : "#2e7d32") + ';">' + item.return_count + '</div></div>';
      }
    }

    const proofPanel = el("returnsDetailProof");
    const proofLink = el("returnsProofLink");
    if (item.proof_url && proofPanel && proofLink) {
      proofPanel.style.display = "block";
      proofLink.href = item.proof_url;
      proofLink.textContent = "View attached document";
    } else if (proofPanel) {
      proofPanel.style.display = "none";
    }

    const remarksPanel = el("returnsAuditorRemarks");
    const remarksText = el("returnsAuditorRemarksText");
    if (item.auditor_remarks && remarksPanel && remarksText) {
      remarksPanel.style.display = "block";
      remarksText.textContent = item.auditor_remarks;
    } else if (remarksPanel) {
      remarksPanel.style.display = "none";
    }

    const resubmitSection = el("returnsResubmitSection");
    const editableFields = el("returnsEditableFields");
    if (state.role === "treasurer" && !item.resubmitted && resubmitSection) {
      resubmitSection.style.display = "block";
      el("r_tv_id").value = item.tv_id;
      el("r_table_name").value = item.table_name;
      el("r_record_id").value = item.record_id;
      if (editableFields) {
        editableFields.innerHTML = "";
        (item.fields || []).forEach(f => {
          const div = document.createElement("div");
          div.className = "form-group";
          const label = document.createElement("label");
          label.textContent = f.label + (f.required ? " *" : "");
          label.style.fontSize = "0.8rem";
          label.style.fontWeight = "600";
          label.style.color = "#1b5e20";
          div.appendChild(label);
          let input;
          if (f.type === "select" && f.options) {
            input = document.createElement("select");
            f.options.forEach(opt => {
              const o = document.createElement("option");
              o.value = opt;
              o.textContent = opt;
              if (opt === f.value) o.selected = true;
              input.appendChild(o);
            });
          } else if (f.type === "textarea") {
            input = document.createElement("textarea");
            input.value = f.value || "";
            input.rows = 3;
          } else if (f.type === "file") {
            div.style.display = "none";
            return;
          } else {
            input = document.createElement("input");
            input.type = f.type || "text";
            input.value = f.value || "";
          }
          if (input) {
            input.name = f.name;
            input.required = f.required;
            input.style.cssText = "width:100%;padding:8px 12px;border-radius:6px;border:1px solid #cfdccc;font:inherit;background:#fbfdfb;";
            div.appendChild(input);
          }
          editableFields.appendChild(div);
        });
        state.originalFormValues = serializeEditableFields();
      }
    } else if (resubmitSection) {
      resubmitSection.style.display = "none";
    }
  }

  function serializeEditableFields() {
    const data = {};
    const inputs = el("returnsEditableFields")?.querySelectorAll("input, select, textarea");
    if (inputs) {
      inputs.forEach(inp => { data[inp.name] = inp.value; });
    }
    return data;
  }

  function detectChanges() {
    const current = serializeEditableFields();
    return JSON.stringify(current) !== JSON.stringify(state.originalFormValues);
  }

  window.closeReturnsDetail = function () {
    const panel = el("returnsDetailsPanel");
    if (panel) panel.style.display = "none";
    state.selected = null;
  };

  window.submitReturnCorrection = async function (e) {
    e.preventDefault();
    if (state.isSubmitting) { showToast("Already submitting...", true); return; }

    const confirmed = await Swal.fire({
      title: "Resubmit?",
      text: "Confirm resubmission of this record to the auditor queue.",
      icon: "question",
      showCancelButton: true,
      confirmButtonColor: "#1b5e20",
      confirmButtonText: "Yes, resubmit",
      cancelButtonText: "Cancel",
    });
    if (!confirmed.isConfirmed) return;

    if (!detectChanges()) {
      const noChange = await Swal.fire({
        title: "No Changes Detected",
        text: "You haven't modified any fields. Submit anyway?",
        icon: "warning",
        showCancelButton: true,
        confirmButtonColor: "#1b5e20",
        confirmButtonText: "Submit anyway",
        cancelButtonText: "Go back",
      });
      if (!noChange.isConfirmed) return;
    }

    state.isSubmitting = true;
    const btn = el("r_submit_btn");
    if (btn) { btn.disabled = true; btn.textContent = "Submitting..."; }

    const tableName = el("r_table_name").value;
    const recordId = el("r_record_id").value;
    const fd = new FormData();
    const inputs = el("returnsEditableFields")?.querySelectorAll("input, select, textarea");
    if (inputs) {
      inputs.forEach(inp => { fd.append(inp.name, inp.value); });
    }
    const fileInput = el("r_file_input");
    if (fileInput?.files?.length) fd.append("proof_file", fileInput.files[0]);

    try {
      const resp = await fetch("/api/treasurer/resubmit/" + tableName + "/" + recordId + "/", {
        method: "POST",
        body: fd,
        headers: { [CSRF_HEADER]: getCSRFToken() },
        credentials: "same-origin",
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) { showToast(data?.error || "Resubmit failed", true); state.isSubmitting = false; if (btn) { btn.disabled = false; btn.textContent = "Resubmit"; } return; }

      showToast("Record resubmitted successfully.");
      window.closeReturnsDetail();
      await loadReturns();
    } catch (err) {
      showToast("Network error while submitting.", true);
    }
    state.isSubmitting = false;
    if (btn) { btn.disabled = false; btn.textContent = "Resubmit"; }
  };

  function wireTabs() {
    const container = el("returnsFilterTabs");
    if (!container) return;
    container.querySelectorAll("[data-tab]").forEach(btn => {
      btn.addEventListener("click", function () {
        container.querySelectorAll("[data-tab]").forEach(b => { b.className = "btn-brand"; b.style.opacity = "0.7"; });
        this.className = "btn-brand btn-brand-primary";
        this.style.opacity = "1";
        state.activeTab = this.dataset.tab;
        applyFilter();
      });
    });
  }

  function init() {
    const panel = getPanel();
    if (!panel) return;
    state.role = panel.dataset.role || "";
    wireTabs();
    loadReturns();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
