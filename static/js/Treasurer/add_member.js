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

    const photoInput = document.getElementById("prof_photo_file");
    const photoFile =
      photoInput && photoInput.files && photoInput.files.length
        ? photoInput.files[0]
        : null;

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
    if (photoFile) fd.append("prof_photo_file", photoFile);

    // ==========================================
    // MODULE 2: DYNAMIC STREAMLINED PAYMENT PARSING
    // ==========================================
    const paymentRequired = document.getElementById(
      "enroll_payment_required_toggle",
    ).checked;
    fd.append("payment_required", paymentRequired ? "true" : "false");

    if (paymentRequired) {
      const feeMethod = getFormValue("enroll_fee_method").trim();
      const feeDate = getFormValue("enroll_fee_date").trim();
      let feeAmount = getFormValue("enroll_fee_amount").trim();

      // If field is left empty by encoder, fall back to standard 500.00 base constraint
      if (!feeAmount) {
        feeAmount = "500.00";
      }

      if (!feeMethod)
        return showToast(
          "Payment Method is required when logging a payment.",
          true,
        );
      if (!feeDate)
        return showToast(
          "Payment Date is required when logging a payment.",
          true,
        );
      if (parseFloat(feeAmount) <= 0 || isNaN(parseFloat(feeAmount))) {
        return showToast(
          "Payment Amount must be a positive numeric value.",
          true,
        );
      }

      fd.append("fee_method", feeMethod);
      fd.append("fee_date", feeDate);
      fd.append("fee_amount", feeAmount);

      // ==========================================
      // MODULE 3: GRANULAR RECEIPT AUDIT PARSING
      // ==========================================
      const receiptRequired = document.getElementById(
        "enroll_receipt_required_toggle",
      ).checked;
      fd.append("receipt_required", receiptRequired ? "true" : "false");

      if (receiptRequired) {
        const feeRef = getFormValue("enroll_fee_ref").trim();
        const feeEncoder = getFormValue("enroll_fee_encoder").trim();

        const receiptInput = document.getElementById("enroll_fee_photo_file");
        const receiptFile =
          receiptInput && receiptInput.files && receiptInput.files.length
            ? receiptInput.files[0]
            : null;

        if (!feeRef)
          return showToast("Receipt / Reference Number is required.", true);
        if (!feeEncoder)
          return showToast("Encoder description identity is required.", true);
        if (!receiptFile)
          return showToast(
            "Please upload an official photo proof of the payment receipt.",
            true,
          );

        fd.append("fee_ref", feeRef);
        fd.append("fee_encoder", feeEncoder);
        fd.append("fee_photo_file", receiptFile);
      }
    }

    const csrf = getCSRFToken();

    // ==========================================
    // MODULE 4: UNIFIED NETWORK AJAX DESTINATION
    // ==========================================
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
        return;
      }

      // Sync window database matrix structure if context array is present
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
        window.renderMembersTable();
      }

      // Clean up interactive template flags post successfully completing save execution
      form.reset();

      const profPreview = document.getElementById("prof_preview");
      if (profPreview) profPreview.style.display = "none";

      const feePreview = document.getElementById("enroll_fee_preview");
      if (feePreview) feePreview.style.display = "none";

      // Re-trigger view display driver functions to enforce default structural hiding layout rules
      if (typeof window.togglePaymentSectionVisibility === "function")
        window.togglePaymentSectionVisibility();
      if (typeof window.toggleReceiptFieldsVisibility === "function")
        window.toggleReceiptFieldsVisibility();

      showToast("Streamlined Member Profile logged successfully!", false);
      if (data.email_sent && email) {
        showToast(`Welcome email sent to ${email}`, false);
      }
    } catch (err) {
      showToast(
        "Network/server error while handling your execution request.",
        true,
      );
    }
  }

  function init() {
    const form = document.getElementById(FORM_ID);
    if (!form) return;

    window.handleMemberSubmit = handleSubmit;
    form.addEventListener("submit", handleSubmit);
  }

  document.addEventListener("turbo:load", init);

  // Expose visibility handlers globally for the HTML onchange attributes
  window.togglePaymentSectionVisibility = function () {
    const isChecked = document.getElementById(
      "enroll_payment_required_toggle",
    ).checked;
    const container = document.getElementById("enroll_corePaymentContainer");
    const fields = ["enroll_fee_method", "enroll_fee_date", "enroll_fee_amount"];

    if (isChecked) {
      container.style.display = "block";
      fields.forEach((id) =>
        document.getElementById(id).setAttribute("required", "true"),
      );
    } else {
      container.style.display = "none";
      fields.forEach((id) =>
        document.getElementById(id).removeAttribute("required"),
      );
      document.getElementById("enroll_receipt_required_toggle").checked = false;
      window.toggleReceiptFieldsVisibility();
    }
  };

  window.toggleReceiptFieldsVisibility = function () {
    const isChecked = document.getElementById(
      "enroll_receipt_required_toggle",
    ).checked;
    const container = document.getElementById("enroll_auditFieldsContainer");
    const fields = ["enroll_fee_ref", "enroll_fee_encoder"];

    if (
      isChecked &&
      document.getElementById("enroll_payment_required_toggle").checked
    ) {
      container.style.display = "block";
      fields.forEach((id) =>
        document.getElementById(id).setAttribute("required", "true"),
      );
    } else {
      container.style.display = "none";
      fields.forEach((id) =>
        document.getElementById(id).removeAttribute("required"),
      );
    }
  };
})();
