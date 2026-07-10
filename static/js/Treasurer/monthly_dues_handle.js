function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatCurrencyPHP(num) {
    const n = typeof num === "number" ? num : parseFloat(num || 0);
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
    }).format(n);
  }

  let historyViewMode = "batch";

  async function apiGetOtcDues() {
    const res = await fetch("/api/treasurer/monthly-dues/otc/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    return res.json();
  }

  async function apiAddOtcDues(formData) {
    const res = await fetch("/api/treasurer/monthly-dues/otc/add/", {
      method: "POST",
      credentials: "same-origin",
      body: formData,
    });
    return res.json();
  }

  function renderOtcTable(rows) {
    const table = byId("otcTable");
    if (!table) return;
    const actualTbody = table.querySelector("tbody");
    if (!actualTbody) return;

    actualTbody.innerHTML = "";

    if (!rows || rows.length === 0) {
      actualTbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#757575;">No OTC dues payments recorded</td></tr>';
      return;
    }

    rows.forEach((o) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:600;color:#1b5e20;">${escapeHtml(o.ref || "")}</td>
        <td>${escapeHtml(o.member_name || "")} <br><span style="font-size:0.75rem;color:#757575;">Code: ${escapeHtml(o.member_id || "")}</span></td>
        <td><span class="badge-zero badge-green" style="font-size:0.75rem;">${escapeHtml(o.month || "")}</span></td>
        <td style="font-weight:600;">${escapeHtml(formatCurrencyPHP(o.amount))}</td>
        <td>${escapeHtml(o.method || "")} <br><span style="font-size:0.75rem;color:#757575;">Date: ${escapeHtml(o.date || "")}</span></td>
      `;
      actualTbody.appendChild(tr);
    });
  }

  async function apiGetSalaryDues() {
    const res = await fetch("/api/treasurer/monthly-dues/salary/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    return res.json();
  }

  async function apiAddSalaryDues(formData) {
    const res = await fetch("/api/treasurer/monthly-dues/salary/add/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: formData,
    });
    return res.json();
  }

  function renderSalaryTable(data) {
    const table = byId("salaryTable");
    if (!table) return;
    const thead = byId("salaryTableHead");
    const tbody = table.querySelector("tbody");
    if (!thead || !tbody) return;

    if (historyViewMode === "batch") {
      renderSalaryBatchView(thead, tbody, data.batches || []);
    } else {
      renderSalaryListView(thead, tbody, data.salary_dues || []);
    }
  }

  function renderSalaryBatchView(thead, tbody, batches) {
    thead.innerHTML = `
      <tr>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-layer-group" title="Batch Reference"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-calendar" title="Month"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-users" title="Members"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-coins" title="Total Amount"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-eye" title="Action"></i></th>
      </tr>
    `;
    tbody.innerHTML = "";

    if (!batches || batches.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#757575;">No batches recorded</td></tr>';
      return;
    }

    batches.forEach((b) => {
      const tr = document.createElement("tr");
      tr.className = "salary-batch-row";
      tr.style.cursor = "pointer";
      tr.innerHTML = `
        <td style="font-weight:600;color:#1b5e20;">${escapeHtml(b.batch_reference || "")}</td>
        <td><span class="badge-zero badge-green" style="font-size:0.75rem;">${escapeHtml(b.month || "")}</span></td>
        <td>${b.member_count} member${b.member_count !== 1 ? "s" : ""}</td>
        <td style="font-weight:600;">${escapeHtml(formatCurrencyPHP(b.total_amount))}</td>
        <td><button type="button" class="btn-brand btn-brand-secondary batch-view-details" style="padding:4px 10px;font-size:0.75rem;border-radius:6px;">View Details</button></td>
      `;
      tr.querySelector(".batch-view-details").addEventListener(
        "click",
        function (e) {
          e.stopPropagation();
          showBatchDetailModal(b);
        },
      );
      tr.addEventListener("click", function () {
        showBatchDetailModal(b);
      });
      tbody.appendChild(tr);
    });
  }

  function renderSalaryListView(thead, tbody, rows) {
    thead.innerHTML = `
      <tr>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-receipt" title="Reference #"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-user" title="Member"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-calendar" title="Month"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-coins" title="Expected Dues"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-pen" title="Accounting Remarks"></i></th>
        <th style="padding:4px 8px;text-align:center;"><i class="fa-solid fa-file-lines" title="Audit"></i></th>
      </tr>
    `;
    tbody.innerHTML = "";

    if (!rows || rows.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:#757575;">No salary deduction remittances recorded</td></tr>';
      return;
    }

    rows.forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:600;color:#1b5e20;">${escapeHtml(s.ref || "")}</td>
        <td>${escapeHtml(s.member_name || "")} <br><span style="font-size:0.75rem;color:#757575;">Code: ${escapeHtml(s.member_id || "")}</span></td>
        <td><span class="badge-zero badge-green" style="font-size:0.75rem;">${escapeHtml(s.month || "")}</span></td>
        <td style="font-weight:600;">${escapeHtml(formatCurrencyPHP(s.amount))}</td>
        <td style="font-weight:600;">${escapeHtml(s.remarks || "")}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function showBatchDetailModal(batch) {
    const modal = byId("batchDetailModal");
    const title = byId("batchDetailTitle");
    const content = byId("batchDetailContent");
    if (!modal || !title || !content) return;

    title.textContent = "Batch Details";

    let html = `
      <div style="margin-bottom:12px;">
        <div style="font-size:0.95rem;color:#1b5e20;font-weight:600;">${escapeHtml(batch.batch_reference || "N/A")}</div>
        <div style="margin-top:6px;font-size:0.85rem;color:#555;">
          Processed By:
          <span style="display:inline-block;background:rgba(76,175,80,0.18);color:#2e7d32;padding:2px 12px;border-radius:20px;font-weight:600;font-size:0.85rem;margin-left:4px;">${escapeHtml(batch.recorded_by || "Unknown")}</span>
        </div>
      </div>
      <div class="batch-detail-summary">
        <div class="batch-detail-summary-card">
          <div style="font-size:0.75rem;color:#757575;">Month</div>
          <div style="font-weight:600;color:#1b5e20;">${escapeHtml(batch.month || "")}</div>
        </div>
        <div class="batch-detail-summary-card">
          <div style="font-size:0.75rem;color:#757575;">Members</div>
          <div style="font-weight:600;color:#1b5e20;">${batch.member_count}</div>
        </div>
        <div class="batch-detail-summary-card">
          <div style="font-size:0.75rem;color:#757575;">Total Amount</div>
          <div style="font-weight:600;color:#1b5e20;">${escapeHtml(formatCurrencyPHP(batch.total_amount))}</div>
        </div>
      </div>
    `;

    const members = batch.members || [];
    if (members.length === 0) {
      html += '<p style="color:#757575;">No members in this batch.</p>';
    } else {
      html += `
        <div class="batch-detail-table-wrap">
          <table class="custom-table batch-detail-table">
            <thead>
              <tr>
                <th style="padding:4px 8px;">#</th>
                <th style="padding:4px 8px;">Member Name</th>
                <th style="padding:4px 8px;">Amount</th>
              </tr>
            </thead>
            <tbody>
      `;
      members.forEach((m, idx) => {
        html += `
          <tr>
            <td style="padding:4px 8px;text-align:center;">${idx + 1}</td>
            <td style="padding:4px 8px;">${escapeHtml(m.member_name || "")}</td>
            <td style="padding:4px 8px;">${escapeHtml(formatCurrencyPHP(m.amount))}</td>
          </tr>
        `;
      });
      html += `
            </tbody>
          </table>
        </div>
      `;
    }

    content.innerHTML = html;
    modal.style.display = "flex";
  }

  function closeBatchDetailModal() {
    const modal = byId("batchDetailModal");
    if (modal) modal.style.display = "none";
  }
  window.closeBatchDetailModal = closeBatchDetailModal;

  async function fetchSalaryHistory() {
    const list = await apiGetSalaryDues();
    if (!list || !list.ok) {
      showToast(
        list && list.error
          ? list.error
          : "Failed to refresh salary deduction history.",
        true,
      );
      return;
    }
    renderSalaryTable(list);
    window.db = window.db || {};
    window.db.salary_deductions = list.salary_dues || [];
    window.db.salary_batches = list.batches || [];
    if (typeof window.saveSystemDatabase === "function")
      window.saveSystemDatabase();
    if (typeof window.updateKPICards === "function") window.updateKPICards();
  }

  async function fetchAndRenderOtc() {
    const list = await apiGetOtcDues();
    if (!list || !list.ok) {
      showToast(
        list && list.error ? list.error : "Failed to refresh OTC dues.",
        true,
      );
      return;
    }
    renderOtcTable(list.otc_dues || []);
    window.db = window.db || {};
    window.db.otc_dues = list.otc_dues || [];
    if (typeof window.saveSystemDatabase === "function")
      window.saveSystemDatabase();
    if (typeof window.updateKPICards === "function") window.updateKPICards();
  }

  async function fetchMembers() {
    const resp = await fetch("/api/treasurer/members/list/", {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Failed to load members.");
    }
    return data.members || [];
  }

  function populateDuesDropdowns(members) {
    ["otc_member", "sal_member"].forEach((id) => {
      const sel = byId(id);
      if (!sel) return;
      sel.innerHTML = '<option value="">Select Associated Member</option>';
      members.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.member_id;
        opt.textContent = `${m.full_name}`;
        sel.appendChild(opt);
      });
    });
  }

  function init() {
    // Expose helpers globally
    window.triggerFileUpload =
      window.triggerFileUpload ||
      function (id) {
        const el = byId(id);
        if (el) el.click();
      };

    window.showAttachedPreview =
      window.showAttachedPreview ||
      function (input, labelId) {
        if (input.files && input.files.length > 0) {
          const el = byId(labelId);
          if (el) el.style.display = "block";
        }
      };

    window.fetchSalaryHistory = fetchSalaryHistory;

    // OTC
    const otcForm = byId("otcDuesForm");
    if (otcForm) {
      // Disable inline handler if it exists; we handle submit here.
      otcForm.removeAttribute("onsubmit");

      otcForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          const formData = new FormData(otcForm);

          const out = await apiAddOtcDues(formData);
          if (!out || !out.ok) {
            showToast(
              out && out.error ? out.error : "Failed to record OTC dues.",
              true,
            );
            return;
          }

          showToast("Over-the-Counter Monthly Dues recorded.", false);
          await fetchAndRenderOtc();
          otcForm.reset();
        } catch (err) {
          showToast("Network/server error while recording OTC dues.", true);
        }
      });

      fetchAndRenderOtc().catch(() => {});
    }

    // Salary: ensure global handler used by template runs the Django workflow.
    window.handleSalarySubmit = async function handleSalarySubmit(event) {
      event.preventDefault();
      const salaryForm = byId("salaryForm");
      if (!salaryForm) return;

      const salRefInput = byId("sal_ref");
      const salRefValue = salRefInput ? (salRefInput.value || "").trim() : "";

      try {
        const formData = new FormData(salaryForm);
        if (salRefValue) {
          formData.set("sal_ref", salRefValue);
        }
        const out = await apiAddSalaryDues(formData);
        if (!out || !out.ok) {
          showToast(
            out && out.error ? out.error : "Failed to record salary deduction.",
            true,
          );
          return;
        }

        showToast("Salary deduction remittance recorded.", false);
        await fetchSalaryHistory();
        salaryForm.reset();

        const preview = byId("sal_preview");
        if (preview) preview.style.display = "none";
      } catch (err) {
        showToast(
          "Network/server error while recording salary deduction.",
          true,
        );
      }
    };

    // Optional: auto-load salary ledger
    const salaryTable = byId("salaryTable");
    if (salaryTable) {
      fetchSalaryHistory().catch(() => {});
    }

    // History view toggle
    document.querySelectorAll(".history-view-toggle").forEach((btn) => {
      btn.addEventListener("click", function () {
        historyViewMode = this.dataset.view;
        document.querySelectorAll(".history-view-toggle").forEach((b) => {
          b.classList.remove("btn-brand-primary");
          b.style.opacity = "0.7";
        });
        this.classList.add("btn-brand-primary");
        this.style.opacity = "1";
        const db = window.db || {};
        renderSalaryTable({
          salary_dues: db.salary_deductions || [],
          batches: db.salary_batches || [],
        });
      });
    });

    // Populate dropdowns from database
    fetchMembers()
      .then(populateDuesDropdowns)
      .catch(() => {});

    // --- Bulk Salary Deduction ---
    initBulkSalary();
  }

  function generateBatchRef() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const rand = Math.random().toString(36).substring(2, 6).toUpperCase();
    return `SAL-${y}${m}-${rand}`;
  }

  function initBulkSalary() {
    const bulkPanel = byId("salary-bulk-panel");
    if (!bulkPanel) return;

    // Tab switching
    document.querySelectorAll(".salary-tab-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        const tab = this.dataset.tab;
        document.querySelectorAll(".salary-tab-btn").forEach((b) => {
          b.classList.remove("btn-brand-primary");
          b.style.opacity = "0.7";
        });
        this.classList.add("btn-brand-primary");
        this.style.opacity = "1";

        const individualPanel = byId("salary-individual-panel");
        const bulkPanelEl = byId("salary-bulk-panel");
        if (individualPanel)
          individualPanel.style.display = tab === "individual" ? "" : "none";
        if (bulkPanelEl)
          bulkPanelEl.style.display = tab === "bulk" ? "" : "none";
        triggerPremiumGlow();
      });
    });

    // Auto-gen batch reference
    const autoGenBtn = byId("bulk_autogen_ref");
    const batchRefInput = byId("bulk_batch_ref");
    if (autoGenBtn && batchRefInput) {
      autoGenBtn.addEventListener("click", function () {
        batchRefInput.value = generateBatchRef();
      });
    }

    // Preview button
    const previewBtn = byId("bulk_preview_btn");
    const memberSection = byId("bulk-member-section");
    const memberTbody = byId("bulk-member-tbody");
    const memberCount = byId("bulk-member-count");
    const statusMsg = byId("bulk-status-msg");
    const processBtn = byId("bulk_process_btn");

    let previewData = { members: [], expected_amount: 0 };

    if (previewBtn) {
      previewBtn.addEventListener("click", async function () {
        const month = byId("bulk_sal_month");
        if (!month || !month.value) {
          showToast("Please select a deduction month.", true);
          return;
        }

        previewBtn.disabled = true;
        previewBtn.textContent = "Loading...";

        try {
          const fd = new FormData();
          fd.set("sal_month", month.value);
          const resp = await fetch(
            "/api/treasurer/monthly-dues/salary/bulk-preview/",
            {
              method: "POST",
              credentials: "same-origin",
              headers: { "X-CSRFToken": getCookie("csrftoken") },
              body: fd,
            },
          );
          const data = await resp.json();
          if (!data.ok) {
            showToast(data.error || "Preview failed.", true);
            previewBtn.disabled = false;
            previewBtn.textContent = "Preview Members";
            return;
          }

          previewData = data;
          renderBulkMemberTable(data);
          if (memberSection) memberSection.style.display = "block";
          if (statusMsg) {
            const skipped = data.already_processed || 0;
            const total = data.total_active || 0;
            statusMsg.textContent = `${total} active members, ${skipped} already processed this month.`;
          }
          updateProcessBtn();
        } catch (err) {
          showToast("Network error loading preview.", true);
        }

        previewBtn.disabled = false;
        previewBtn.textContent = "Preview Members";
      });
    }

    function updateBulkAmountBadge() {
      const perMemberEl = byId("bulk-per-member");
      const totalEl = byId("bulk-total-display");
      const totalAmountEl = byId("bulk-total-amount");
      if (!perMemberEl || !totalEl || !totalAmountEl) return;
      const amount = previewData.expected_amount || 0;
      perMemberEl.textContent = formatCurrencyPHP(amount).replace("₱", "");
      const checked = document.querySelectorAll("#bulk-member-tbody .bulk-member-cb:checked").length;
      if (checked > 0 && amount > 0) {
        totalEl.style.display = "inline";
        totalAmountEl.textContent = formatCurrencyPHP(amount * checked).replace("₱", "");
      } else {
        totalEl.style.display = "none";
      }
    }

    function renderBulkMemberTable(data) {
      if (!memberTbody) return;
      memberTbody.innerHTML = "";
      const members = data.members || [];
      if (memberCount) {
        memberCount.textContent = `${members.length} members`;
      }
      updateBulkAmountBadge();
      members.forEach((m) => {
        const tr = document.createElement("tr");
        const dupLabel = m.already_exists
          ? ' <span style="color:#d89600;font-size:0.75rem;">[dup]</span>'
          : "";
        tr.innerHTML = `
          <td><input type="checkbox" class="bulk-member-cb" value="${m.member_id}" ${m.default_checked ? "checked" : ""}></td>
          <td>${escapeHtml(m.member_name)}${dupLabel}</td>
          <td>${escapeHtml(m.department || "—")}</td>
          <td>${escapeHtml(m.status || "—")}</td>
        `;
        memberTbody.appendChild(tr);
      });
    }

    // Select All / None / Invert
    const selectAllBtn = byId("bulk_select_all");
    const selectNoneBtn = byId("bulk_select_none");
    const selectInvertBtn = byId("bulk_select_invert");

    function getMemberCheckboxes() {
      return document.querySelectorAll("#bulk-member-tbody .bulk-member-cb");
    }

    function updateProcessBtn() {
      if (!processBtn) return;
      const checked = document.querySelectorAll(
        "#bulk-member-tbody .bulk-member-cb:checked",
      ).length;
      if (checked > 0) {
        processBtn.disabled = false;
        processBtn.textContent = `Process ${checked} Member${checked !== 1 ? "s" : ""}`;
      } else {
        processBtn.disabled = true;
        processBtn.textContent = "Process Members";
      }
      updateBulkAmountBadge();
    }

    if (selectAllBtn) {
      selectAllBtn.addEventListener("click", function () {
        getMemberCheckboxes().forEach((cb) => {
          cb.checked = true;
        });
        updateProcessBtn();
      });
    }
    if (selectNoneBtn) {
      selectNoneBtn.addEventListener("click", function () {
        getMemberCheckboxes().forEach((cb) => {
          cb.checked = false;
        });
        updateProcessBtn();
      });
    }
    if (selectInvertBtn) {
      selectInvertBtn.addEventListener("click", function () {
        getMemberCheckboxes().forEach((cb) => {
          cb.checked = !cb.checked;
        });
        updateProcessBtn();
      });
    }
    if (memberTbody) {
      memberTbody.addEventListener("change", function (e) {
        if (e.target.classList.contains("bulk-member-cb")) {
          updateProcessBtn();
        }
      });
    }

    // Process button
    if (processBtn) {
      processBtn.addEventListener("click", async function () {
        const month = byId("bulk_sal_month");
        const batchRef = byId("bulk_batch_ref");
        const summary = byId("bulk_summary");
        const fileInput = byId("bulk_photo_file");

        if (!month || !month.value) {
          showToast("Please select a deduction month.", true);
          return;
        }
        if (!batchRef || !batchRef.value.trim()) {
          showToast("Please enter a batch reference.", true);
          return;
        }

        const checkedIds = [];
        getMemberCheckboxes().forEach((cb) => {
          if (cb.checked) checkedIds.push(parseInt(cb.value));
        });

        if (checkedIds.length === 0) {
          showToast("No members selected.", true);
          return;
        }

        processBtn.disabled = true;
        processBtn.textContent = "Processing...";

        try {
          const fd = new FormData();
          fd.set("sal_month", month.value);
          fd.set("batch_ref", batchRef.value.trim());
          fd.set("summary", summary ? summary.value.trim() : "");
          fd.set("member_ids", JSON.stringify(checkedIds));
          if (fileInput && fileInput.files && fileInput.files[0]) {
            fd.set("sal_photo_file", fileInput.files[0]);
          }

          const resp = await fetch(
            "/api/treasurer/monthly-dues/salary/bulk-process/",
            {
              method: "POST",
              credentials: "same-origin",
              headers: { "X-CSRFToken": getCookie("csrftoken") },
              body: fd,
            },
          );
          const data = await resp.json();
          if (!data.ok) {
            showToast(data.error || "Bulk processing failed.", true);
            processBtn.disabled = false;
            processBtn.textContent = "Process Members";
            return;
          }

          showToast(
            `Created ${data.processed} salary deductions for ${data.month} (${data.skipped} skipped).`,
            false,
          );

          // Reset UI
          if (memberSection) memberSection.style.display = "none";
          if (memberTbody) memberTbody.innerHTML = "";
          if (statusMsg) statusMsg.textContent = "";
          if (month) month.value = "";
          if (batchRef) batchRef.value = "";
          if (summary) summary.value = "";
          if (fileInput) fileInput.value = "";
          const bulkPreview = byId("bulk_preview");
          if (bulkPreview) bulkPreview.style.display = "none";
          updateProcessBtn();
          previewData = { members: [], expected_amount: 0 };

          // Refresh history
          fetchSalaryHistory();
        } catch (err) {
          showToast(
            "Network error during bulk processing. Use Individual Entry tab as fallback.",
            true,
          );
          processBtn.disabled = false;
          processBtn.textContent = "Process Members";
        }
      });
    }

    triggerPremiumGlow();
  }

  function triggerPremiumGlow() {
    const btns = document.querySelectorAll(".salary-tab-btn");
    btns.forEach((b) => b.classList.add("premium-active"));
    setTimeout(() => {
      btns.forEach((b) => b.classList.remove("premium-active"));
    }, 2000);
  }

  window.addEventListener("turbo:load", init);
})();
