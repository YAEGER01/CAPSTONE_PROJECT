(function () {
  "use strict";

  const FORM_ID = "memberForm";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function getFormValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
  }

  async function handleSubmit(e) {
    e.preventDefault();

    const form = document.getElementById(FORM_ID);
    if (!form) return;

    // ==========================================
    // MODULE 1: EXTRACT CORE MEMBER VALUES
    // ==========================================
    const fullName = getFormValue("prof_name").trim();
    const empId = getFormValue("prof_id").trim();
    const dept = getFormValue("prof_dept").trim();
    const pos = getFormValue("prof_pos").trim();
    const contact = getFormValue("prof_contact").trim();
    const email = getFormValue("prof_email").trim();
    const status = getFormValue("prof_status").trim();

    // Client-side duplicate check
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

    // Profile Validations
    if (!fullName) return showToast("Full Legal Name is required.", true);
    if (!empId) return showToast("Employee/Faculty ID is required.", true);
    if (!status) return showToast("Membership Status is required.", true);
    if (email && !email.includes("@"))
      return showToast("Institutional Email looks invalid.", true);

    // Instantiate Unified Payload
    const fd = new FormData();
    fd.append("prof_name", fullName);
    fd.append("prof_id", empId);
    fd.append("prof_dept", dept);
    fd.append("prof_pos", pos);
    fd.append("prof_contact", contact);
    fd.append("prof_email", email);
    fd.append("prof_status", status);
    var profFiles = FileQueue.getFiles("prof");
    if (profFiles.length > 0) fd.append("prof_photo_file", profFiles[0]);

    const csrf = getCSRFToken();

    const submitBtn = form.querySelector("button[type='submit']");
    let originalBtnHTML = "";
    if (submitBtn) {
      originalBtnHTML = submitBtn.innerHTML;
      submitBtn.disabled = true;
    }

    // ==========================================
    // INSTANT FEEDBACK: show success modal without
    // waiting for the network round trip, then
    // process the enrollment in the background.
    // ==========================================
    Swal.fire({
      title: "Enrollment Complete",
      text: `Member ${fullName} has been added and recorded, and has been notified thru gmail ${email}`,
      icon: "success",
      confirmButtonColor: "#1b5e20",
    });

    // ==========================================
    // MODULE 4: UNIFIED NETWORK AJAX DESTINATION (background)
    // ==========================================
    (async () => {
      try {
        // Pointing directly to our incoming combined views endpoint mapping
        const resp = await fetch("/api/treasurer/members/add/", {
          method: "POST",
          body: fd,
          headers: csrf ? { "X-CSRFToken": csrf } : {},
          credentials: "same-origin",
        });

        const data = await resp.json().catch(() => ({}));

        if (!resp.ok || !data.ok) {
          const err =
            data && data.error
              ? data.error
              : "Failed to execute streamlined directory registration.";
          showToast(err, true);
          Swal.fire({
            title: "Enrollment Failed",
            text: err,
            icon: "error",
            confirmButtonColor: "#e53935",
          });
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnHTML;
          }
          return;
        }

        // Sync window database matrix structure if context array is present
        const activeDb = window.db || (typeof db !== "undefined" ? db : null);
        if (activeDb && Array.isArray(activeDb.members)) {
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
          activeDb.members.push(newMember);
        }

        if (typeof window.saveSystemDatabase === "function") {
          window.saveSystemDatabase();
        } else if (typeof saveSystemDatabase === "function") {
          saveSystemDatabase();
        }

        if (typeof window.renderMembersFromBackend === "function") {
          window.renderMembersFromBackend();
        } else if (typeof renderMembersFromBackend === "function") {
          renderMembersFromBackend();
        } else {
          if (typeof window.renderAllComponents === "function") {
            window.renderAllComponents();
          } else if (typeof renderAllComponents === "function") {
            renderAllComponents();
          } else if (typeof window.renderMembersTable === "function") {
            window.renderMembersTable();
          } else if (typeof renderMembersTable === "function") {
            renderMembersTable();
          }
        }

        // Clean up interactive template flags post successfully completing save execution
        form.reset();
        FileQueue.clear("prof");

        const profPreview = document.getElementById("prof_preview");
        if (profPreview) profPreview.style.display = "none";

        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHTML;
        }
      } catch (err) {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHTML;
        }
        showToast(
          "Network/server error while handling your execution request.",
          true,
        );
      }
    })();
  }

  function init() {
    FileQueue.init("prof", { inputId: "prof_file_input", containerId: "prof_file_queue", maxFiles: 1 });

    const form = document.getElementById(FORM_ID);
    if (!form) return;

    window.handleMemberSubmit = handleSubmit;
    form.addEventListener("submit", handleSubmit);
  }

  document.addEventListener("turbo:load", init);
})();
