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

  function renderSalaryTable(rows) {
    const table = byId("salaryTable");
    if (!table) return;
    const actualTbody = table.querySelector("tbody");
    if (!actualTbody) return;

    actualTbody.innerHTML = "";

    if (!rows || rows.length === 0) {
      actualTbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#757575;">No salary deduction remittances recorded</td></tr>';
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
      actualTbody.appendChild(tr);
    });
  }

  function showToast(message, isError = false) {
    if (typeof window.showToast === "function") {
      window.showToast(message, isError);
      return;
    }
    alert(message);
  }

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
      renderSalaryTable(list.salary_dues || []);
      window.db = window.db || {};
      window.db.salary_deductions = list.salary_dues || [];
      if (typeof window.saveSystemDatabase === "function") window.saveSystemDatabase();
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
      if (typeof window.saveSystemDatabase === "function") window.saveSystemDatabase();
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
      sel.innerHTML = '<option value="">-- Choose Member ID --</option>';
      members.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.member_id;
        opt.textContent = `${m.full_name} (${m.member_id})`;
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

    // Populate dropdowns from database
    fetchMembers()
      .then(populateDuesDropdowns)
      .catch(() => {});
  }

  window.addEventListener("DOMContentLoaded", init);
})();
