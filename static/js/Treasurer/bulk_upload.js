(function () {
  "use strict";

  const BULK_COUNT = 5;

  const RANK_OPTIONS = `
    <option value="">-- Select Academic Rank --</option>
    <optgroup label="Instructor Ranks">
      <option value="Instructor I">Instructor I</option>
      <option value="Instructor II">Instructor II</option>
      <option value="Instructor III">Instructor III</option>
    </optgroup>
    <optgroup label="Assistant Professor Ranks">
      <option value="Assistant Professor I">Assistant Professor I</option>
      <option value="Assistant Professor II">Assistant Professor II</option>
      <option value="Assistant Professor III">Assistant Professor III</option>
      <option value="Assistant Professor IV">Assistant Professor IV</option>
    </optgroup>
    <optgroup label="Associate Professor Ranks">
      <option value="Associate Professor I">Associate Professor I</option>
      <option value="Associate Professor II">Associate Professor II</option>
      <option value="Associate Professor III">Associate Professor III</option>
      <option value="Associate Professor IV">Associate Professor IV</option>
      <option value="Associate Professor V">Associate Professor V</option>
    </optgroup>
    <optgroup label="Full Professor Ranks">
      <option value="Professor I">Professor I</option>
      <option value="Professor II">Professor II</option>
      <option value="Professor III">Professor III</option>
      <option value="Professor IV">Professor IV</option>
      <option value="Professor V">Professor V</option>
      <option value="Professor VI">Professor VI</option>
    </optgroup>
    <optgroup label="Ultimate Rank">
      <option value="College / University Professor">College / University Professor</option>
    </optgroup>
  `;

  const DEPT_OPTIONS = `
    <option value="">-- Select Department / College --</option>
    <option value="College of Education">College of Education</option>
    <option value="College of Agriculture">College of Agriculture</option>
    <option value="College of Information Technology">Information Technology</option>
    <option value="College of Criminology">Criminology</option>
    <option value="College of Business Management">Business Management</option>
    <option value="Add Option">Add Option</option>
  `;

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function generateEmployeeId(fullName) {
    const year = String(new Date().getFullYear()).slice(-2);
    const parts = (fullName || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    const initials = parts
      .map((p) => p.charAt(0).toUpperCase())
      .join("");
    return `EMPL-${year}-${initials}`;
  }

  const MEMBER_COLORS = ["#1b5e20", "#1565c0", "#e65100", "#6a1b9a", "#ad1457"];

  function buildBulkMemberBlock(i) {
    const n = i + 1;
    const color = MEMBER_COLORS[i % MEMBER_COLORS.length];
    return `
      <fieldset class="bulk-member-card" style="border-left: 6px solid ${color};">
        <legend style="color: ${color};">Member ${n}</legend>
        <div class="form-group">
          <label for="bulk_name_${i}">Full Legal Name</label>
          <input type="text" id="bulk_name_${i}" name="member_${i}_name" autocomplete="off" placeholder="e.g., Senator Evelyn Vance" />
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_pos_${i}">Academic Rank</label>
            <select id="bulk_pos_${i}" name="member_${i}_pos" autocomplete="off">${RANK_OPTIONS}</select>
          </div>
          <div class="form-group">
            <label for="bulk_contact_${i}">Contact Number</label>
            <input type="tel" id="bulk_contact_${i}" name="member_${i}_contact" autocomplete="off" placeholder="e.g., 0917-123-4567" />
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_id_${i}">Employee/Faculty ID</label>
            <input type="text" id="bulk_id_${i}" name="member_${i}_id" autocomplete="off" readonly placeholder="Auto Populated" />
          </div>
          <div class="form-group">
            <label for="bulk_dept_${i}">Department</label>
            <select id="bulk_dept_${i}" name="member_${i}_dept" autocomplete="off">${DEPT_OPTIONS}</select>
          </div>
        </div>
        <div class="form-grid-2">
          <div class="form-group">
            <label for="bulk_email_${i}">Institutional Email</label>
            <input type="email" id="bulk_email_${i}" name="member_${i}_email" autocomplete="off" placeholder="e.g., evelyn.v@government.gov" />
          </div>
          <div class="form-group">
            <label for="bulk_status_${i}">Membership Status</label>
            <select id="bulk_status_${i}" name="member_${i}_status" autocomplete="off">
              <option value="Permanent" selected>Permanent</option>
              <option value="Temporary">Temporary</option>
            </select>
          </div>
        </div>
      </fieldset>
    `;
  }

  function renderBulkBlocks() {
    const container = document.getElementById("bulkMemberRows");
    if (!container) return;
    let html = "";
    for (let i = 0; i < BULK_COUNT; i++) html += buildBulkMemberBlock(i);
    container.innerHTML = html;

    for (let i = 0; i < BULK_COUNT; i++) {
      const nameInput = document.getElementById(`bulk_name_${i}`);
      const idInput = document.getElementById(`bulk_id_${i}`);
      if (!nameInput || !idInput) continue;
      nameInput.addEventListener("input", function () {
        idInput.value = generateEmployeeId(nameInput.value);
      });
      const contactInput = document.getElementById(`bulk_contact_${i}`);
      if (contactInput && typeof window.formatPhoneInput === "function") window.formatPhoneInput(contactInput);
    }
  }

  function triggerBulkUpload() {
    const bulkPanel = document.getElementById("bulkEnrollPanel");
    const singlePanel = document.getElementById("singleEnrollPanel");
    if (bulkPanel) {
      bulkPanel.style.display = "block";
      renderBulkBlocks();
    }
    if (singlePanel) singlePanel.style.display = "none";
  }

  function triggerSingleUpload() {
    const bulkPanel = document.getElementById("bulkEnrollPanel");
    const singlePanel = document.getElementById("singleEnrollPanel");
    if (bulkPanel) bulkPanel.style.display = "none";
    if (singlePanel) singlePanel.style.display = "block";
  }

  async function handleBulkSubmit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const btn = form.querySelector('button[type="submit"]');
    const originalBtnText = btn.innerHTML;

    const entries = [];
    for (let i = 0; i < BULK_COUNT; i++) {
      const name = (document.getElementById(`bulk_name_${i}`).value || "").trim();
      if (!name) continue;
      const email = (document.getElementById(`bulk_email_${i}`).value || "").trim();
      if (email && !email.includes("@")) {
        return showToast(`Member ${i + 1}: Institutional Email looks invalid.`, true);
      }
      entries.push({
        prof_name: name,
        prof_id: (document.getElementById(`bulk_id_${i}`).value || "").trim(),
        prof_pos: (document.getElementById(`bulk_pos_${i}`).value || "").trim(),
        prof_contact: (document.getElementById(`bulk_contact_${i}`).value || "").trim(),
        prof_dept: (document.getElementById(`bulk_dept_${i}`).value || "").trim(),
        prof_email: email,
        prof_status: (document.getElementById(`bulk_status_${i}`).value || "Permanent").trim(),
      });
    }

    if (entries.length === 0) {
      return showToast("Please fill in at least one member's Full Legal Name.", true);
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';

    const csrf = getCSRFToken();
    try {
      const resp = await fetch("/api/treasurer/members/batch-add/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ entries }),
        credentials: "same-origin",
      });
      const data = await resp.json().catch(() => ({}));
      const results = (data && data.results) || [];

      const failed = results.filter((r) => !r.ok);
      const succeeded = results.filter((r) => r.ok).length;

      if (typeof window.renderMembersFromBackend === "function") {
        window.renderMembersFromBackend();
      } else if (typeof renderMembersFromBackend === "function") {
        renderMembersFromBackend();
      } else if (typeof window.renderMembersTable === "function") {
        window.renderMembersTable();
      }

      form.reset();
      btn.disabled = false;
      btn.innerHTML = originalBtnText;

      const enrolledNames = results.filter((r) => r.ok).map((r) => r.name);
      if (failed.length === 0) {
        Swal.fire({
          title: "Batch Enrollment Complete",
          html: `<b>Enrolled ${succeeded} member(s):</b><br><br>` +
            enrolledNames.map((n) => `• ${n}`).join("<br>"),
          icon: "success",
          confirmButtonColor: "#1b5e20",
        });
      } else {
        Swal.fire({
          title: "Batch Enrollment Finished",
          html: `<b>${succeeded} enrolled, ${failed.length} failed.</b><br><br>` +
            `<b>Enrolled:</b><br>` + enrolledNames.map((n) => `• ${n}`).join("<br>") +
            `<br><br><b>Failed:</b><br>` + failed.map((f) => `• ${f.name}: ${f.error}`).join("<br>"),
          icon: "warning",
          confirmButtonColor: "#e53935",
        });
      }
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = originalBtnText;
      Swal.fire({
        title: "Error",
        text: "Network/server error while enrolling members.",
        icon: "error",
        confirmButtonColor: "#e53935",
      });
    }
  }

  function init() {
    const bulkForm = document.getElementById("bulkMemberForm");
    if (bulkForm) bulkForm.addEventListener("submit", handleBulkSubmit);
    // Expose toggle handlers for inline onclick attributes
    window.triggerBulkUpload = triggerBulkUpload;
    window.triggerSingleUpload = triggerSingleUpload;
  }

  document.addEventListener("turbo:load", init);
})();
