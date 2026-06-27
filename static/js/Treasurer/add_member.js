(function () {
  "use strict";

  const FORM_ID = "memberForm";
  const TABLE_BODY_SELECTOR = "#memberTable tbody";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    // fallback (common pattern)
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function showToast(message, isError = false) {
    // Reuse existing global helper if present
    if (typeof window.showToast === "function") {
      window.showToast(message, isError);
      return;
    }

    alert(message);
  }

  function getFormValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
  }

  async function handleSubmit(e) {
    e.preventDefault();

    const form = document.getElementById(FORM_ID);
    if (!form) return;

    const fullName = getFormValue("prof_name").trim();
    const empId = getFormValue("prof_id").trim();
    const dept = getFormValue("prof_dept").trim();
    const pos = getFormValue("prof_pos").trim();
    const contact = getFormValue("prof_contact").trim();
    const email = getFormValue("prof_email").trim();
    const status = getFormValue("prof_status").trim();

    // Prevent duplicates on the client (fast UX) using what we already have.
    // True enforcement must still be done server-side in /api/treasurer/members/add/.
    const dupKey = empId;
    if (
      dupKey &&
      window.db &&
      window.db.members &&
      Array.isArray(window.db.members) &&
      window.db.members.some((m) => String(m.id).trim() === `M-${dupKey}`)
    ) {
      return showToast(
        `Member with Employee/Faculty ID ${dupKey} is already enrolled.`,
        true,
      );
    }

    const photoInput = document.getElementById("prof_photo_file");
    const photoFile =
      photoInput && photoInput.files && photoInput.files.length
        ? photoInput.files[0]
        : null;

    // Minimal validation
    if (!fullName) return showToast("Full Legal Name is required.", true);
    if (!empId) return showToast("Employee/Faculty ID is required.", true);
    if (!status) return showToast("Membership Status is required.", true);
    if (email && !email.includes("@"))
      return showToast("Institutional Email looks invalid.", true);

    const fd = new FormData();
    fd.append("prof_name", fullName);
    fd.append("prof_id", empId);
    fd.append("prof_dept", dept);
    fd.append("prof_pos", pos);
    fd.append("prof_contact", contact);
    fd.append("prof_email", email);
    fd.append("prof_status", status);
    if (photoFile) fd.append("prof_photo_file", photoFile);

    const csrf = getCSRFToken();

    try {
      const resp = await fetch("/api/treasurer/members/add/", {
        method: "POST",
        body: fd,
        headers: csrf ? { "X-CSRFToken": csrf } : {},
        credentials: "same-origin",
      });

      const data = await resp.json().catch(() => ({}));

      if (!resp.ok || !data.ok) {
        const err =
          data && data.error ? data.error : "Failed to enroll member.";
        showToast(err, true);
        return;
      }

      // Optional: update UI if the page uses localStorage-based rendering.
      // Prefer: if the page already defines db + renderMembersTable, push there too.
      if (window.db && Array.isArray(window.db.members)) {
        const newMember = {
          id: `M-${data.member.member_id}`,
          name: data.member.full_name,
          facultyId:
            data.member.employee_id || data.member.member_type || empId,
          department: dept,
          position: pos,
          contact: contact,
          email: email,
          status: data.member.membership_status,
        };
        window.db.members.push(newMember);
        if (typeof window.saveSystemDatabase === "function")
          window.saveSystemDatabase();
        if (typeof window.renderAllComponents === "function")
          window.renderAllComponents();
      } else if (typeof window.renderMembersTable === "function") {
        // If no local db, do a soft reload of table.
        window.renderMembersTable();
      }

      form.reset();
      const preview = document.getElementById("prof_preview");
      if (preview) preview.style.display = "none";

      showToast("Member account provisioned into Directory!", false);
    } catch (err) {
      showToast("Network/server error while enrolling member.", true);
    }
  }

  function init() {
    const form = document.getElementById(FORM_ID);
    if (!form) return;

    // Override inline handler if it exists by redefining global function name.
    // This ensures form uses our processor even if template still has onsubmit="handleMemberSubmit(event)".
    window.handleMemberSubmit = handleSubmit;

    // Also attach explicit listener in case inline handler is removed later.
    form.addEventListener("submit", handleSubmit);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
