const SEED_PENDING_PAYMENTS = [
  {
    id: "PAY-901",
    type: "OTC Fee Payment",
    ref: "OR-23194-A",
    amount: 500,
    expected: 500,
    date: "2026-05-10",
    method: "Over-the-Counter Cash",
    month: "N/A - Enrollment Fee",
    encoder: "Assistant Treasurer Juan Dela Cruz",
    memberName: "Dean Alistair Vance",
    facultyId: "FAC-901",
    department: "College of Science",
    position: "Dean",
    contact: "0917-882-1200",
    email: "a.vance@univ.edu",
    memberStatus: "Active",
    auditorName: "Auditor General Maria Santos",
    auditorDate: "2026-06-05 10:22:15",
    auditorRemarks:
      "All Over-the-counter payments crosschecked and verified correct with Landbank vault submissions. Stamp matches receipt details.",
    auditorEvidence: "OFFICIAL_RECEIPT_OR23194A.jpg",
    timeline: [
      {
        time: "2026-05-10 09:15",
        role: "Treasurer",
        name: "Juan Dela Cruz",
        action: "Created Entry",
        note: "Encoded OTC Fee Payment of ₱500.",
      },
      {
        time: "2026-05-10 09:20",
        role: "Treasurer",
        name: "Juan Dela Cruz",
        action: "Uploaded Attachment",
        note: "Attached OFFICIAL_RECEIPT_OR23194A.jpg.",
      },
      {
        time: "2026-05-10 09:21",
        role: "System",
        name: "Automated",
        action: "Route to Auditor",
        note: "Request automatically pushed to Auditor's queue.",
      },
      {
        time: "2026-06-05 10:22",
        role: "Auditor",
        name: "Maria Santos",
        action: "Marked Verified",
        note: "Reviewed attachments. Remark: 'All Over-the-counter payments crosschecked and verified correct.'",
      },
      {
        time: "2026-06-05 10:22",
        role: "System",
        name: "Automated",
        action: "Route to President",
        note: "Request pushed to President's queue.",
      },
    ],
  },
  {
    id: "PAY-902",
    type: "Monthly Dues - OTC",
    ref: "OR-OTC-7411",
    amount: 200,
    expected: 200,
    date: "2026-05-15",
    method: "GCash QR",
    month: "April 2026",
    encoder: "Senior Treasurer Juan Dela Cruz",
    memberName: "Prof. Evangeline Reyes",
    facultyId: "FAC-552",
    department: "College of Arts",
    position: "Professor",
    contact: "0920-771-4491",
    email: "e.reyes@univ.edu",
    memberStatus: "Active",
    auditorName: "Auditor General Maria Santos",
    auditorDate: "2026-06-05 11:15:30",
    auditorRemarks:
      "Checked GCash mobile transaction API log. Fully cleared and verified.",
    auditorEvidence: "GCASH_TRANSFER_RECEIPT_OTC7411.png",
    timeline: [
      {
        time: "2026-05-15 14:10",
        role: "Treasurer",
        name: "Juan Dela Cruz",
        action: "Created Entry",
        note: "Encoded Monthly Dues OTC payment of ₱200.",
      },
      {
        time: "2026-05-15 14:12",
        role: "Treasurer",
        name: "Juan Dela Cruz",
        action: "Uploaded Attachment",
        note: "Attached GCASH_TRANSFER_RECEIPT_OTC7411.png.",
      },
      {
        time: "2026-05-15 14:15",
        role: "System",
        name: "Automated",
        action: "Route to Auditor",
        note: "Request automatically pushed to Auditor's queue.",
      },
      {
        time: "2026-06-05 11:15",
        role: "Auditor",
        name: "Maria Santos",
        action: "Marked Verified",
        note: "Reviewed GCash confirmation transaction reference. Remark: 'Checked GCash mobile transaction API log.'",
      },
      {
        time: "2026-06-05 11:15",
        role: "System",
        name: "Automated",
        action: "Route to President",
        note: "Request pushed to President's queue.",
      },
    ],
  },
];

function formatAuditEvidence(value) {
  const evidence = String(value || "").trim();
  return evidence ? `Evidence: ${evidence}` : "—";
}

function formatAuditRemarks(value) {
  const remarks = String(value || "").trim();
  return (
    remarks ||
    "Auditor verified and forwarded to President for final executive sign-off."
  );
}

function renderPendingPaymentsTable() {
  const tbody = document.querySelector("#pendingPaymentsTable tbody");
  tbody.innerHTML = "";
  if (db.pendingPayments.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#757575;padding:24px;">All payment approvals completed!</td></tr>`;
    return;
  }
  db.pendingPayments.forEach((p) => {
    const tr = document.createElement("tr");
    tr.setAttribute("onclick", `selectPaymentToAudit('${p.id}')`);
    tr.id = `row-${p.id}`;
    tr.innerHTML = `
      <td style="font-weight:600;color:#1b5e20;">${p.ref}</td>
      <td>${p.memberName}</td>
      <td style="font-weight:600;">₱${p.amount.toFixed(2)}</td>
      <td><span class="badge-zero badge-green" style="font-size:0.75rem;">${p.type}</span></td>
      <td><button class="btn-select-glow">Select</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function selectPaymentToAudit(id) {
  document
    .querySelectorAll("#pendingPaymentsTable tr")
    .forEach((tr) => tr.classList.remove("selected-row"));
  const selectedTr = document.getElementById(`row-${id}`);
  if (selectedTr) selectedTr.classList.add("selected-row");

  const item = db.pendingPayments.find((p) => p.id === id);
  if (!item) return;

  document.getElementById("selectedPaymentHeader").innerText =
    `Ruling Request: ${item.id} (${item.type})`;

  document.getElementById("pReadName").innerText = item.memberName;
  document.getElementById("pReadEmpId").innerText = item.facultyId;
  document.getElementById("pReadDept").innerText = item.department;
  document.getElementById("pReadStatus").innerText = item.memberStatus;
  document.getElementById("pReadContact").innerText = item.contact;

  document.getElementById("pReadCovered").innerText = item.month;
  document.getElementById("pReadExpected").innerText =
    `₱${item.expected.toFixed(2)}`;
  document.getElementById("pReadMethod").innerText = item.method;
  document.getElementById("pReadRef").innerText = item.ref;
  document.getElementById("pReadEncoder").innerText = item.encoder;

  const approvedResets = [
    "pApprovedMembershipTypeText",
    "pApprovedMembershipRefText",
    "pApprovedMembershipMonthText",
    "pApprovedMembershipAmountText",
  ];
  approvedResets.forEach((domId) => {
    const el = document.getElementById(domId);
    if (el) el.innerText = "—";
  });

  const djMembers = safeGetDjangoData("django-members-data");
  const djFees = safeGetDjangoData("django-fees-data");

  const memberName = item.memberName;
  const receiptRef = item.ref;

  function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerText = value == null || value === "" ? "—" : String(value);
  }

  const feesList = Array.isArray(djFees?.fees)
    ? djFees.fees
    : Array.isArray(djFees)
      ? djFees
      : [];

  const matchingFee = feesList.find((f) => {
    const ref =
      f?.ref || f?.receipt_number || f?.receiptNumber || f?.receipt || "";
    const member =
      f?.member_name || f?.memberName || f?.member?.member_name || "";
    return ref === receiptRef || (member === memberName && ref === receiptRef);
  });

  if (matchingFee) {
    setText(
      "pApprovedMembershipTypeText",
      matchingFee?.type ||
        matchingFee?.entity ||
        matchingFee?.payment_type ||
        "OTC Membership Fee",
    );
    setText(
      "pApprovedMembershipRefText",
      matchingFee?.ref || matchingFee?.receipt_number || receiptRef,
    );
    setText(
      "pApprovedMembershipMonthText",
      matchingFee?.month_covered ||
        matchingFee?.month ||
        matchingFee?.monthCovered ||
        "—",
    );
    const amt =
      matchingFee?.amount ?? matchingFee?.fee_amount ?? matchingFee?.amountPaid;
    setText(
      "pApprovedMembershipAmountText",
      amt == null ? "—" : `₱${Number(amt).toFixed(2)}`,
    );
  }



  document.getElementById("pAuditByText").innerText = item.auditorName;
  document.getElementById("pAuditDateText").innerText = item.auditorDate;
  document.getElementById("pAuditEvidenceText").innerText = formatAuditEvidence(
    item.auditorEvidence,
  );
  document.getElementById("pAuditRemarksText").innerText = formatAuditRemarks(
    item.auditorRemarks,
  );

  const timelineBody = document.querySelector("#pTimelineTable tbody");
  timelineBody.innerHTML = "";
  item.timeline.forEach((log) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${log.time}</strong></td>
      <td><span class="badge-zero badge-green" style="font-size: 0.72rem;">${log.role}</span></td>
      <td>${log.name}</td>
      <td><strong>${log.action}</strong></td>
      <td>${log.note}</td>
    `;
    timelineBody.appendChild(tr);
  });

  document.getElementById("p_target_id").value = item.id;
  document.getElementById("p_approved_amount").value = item.amount;
}

function clearPaymentApprovalSelection() {
  document
    .querySelectorAll("#pendingPaymentsTable tr")
    .forEach((tr) => tr.classList.remove("selected-row"));
  document.getElementById("selectedPaymentHeader").innerText =
    "No item selected";

  const resets = [
    "pReadName",
    "pReadEmpId",
    "pReadDept",
    "pReadStatus",
    "pReadContact",
    "pReadCovered",
    "pReadExpected",
    "pReadMethod",
    "pReadRef",
    "pReadEncoder",
    "pAuditByText",
    "pAuditDateText",
    "pAuditEvidenceText",
    "pAuditRemarksText",
    "pApprovedMembershipTypeText",
    "pApprovedMembershipRefText",
    "pApprovedMembershipMonthText",
    "pApprovedMembershipAmountText",
  ];
  resets.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerText = "—";
  });

  const timelineBody = document.querySelector("#pTimelineTable tbody");
  timelineBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #757575;">No tracking logs compiled. Select a transaction to generate path timelines.</td></tr>`;

  document.getElementById("paymentApprovalForm").reset();
  handleDecisionChange("p_decision", "p_remarks");
}

function submitPresidentialPaymentDecision(e) {
  e.preventDefault();
  const targetId = document.getElementById("p_target_id").value;
  if (!targetId) {
    showToast(
      "Please select an active transaction reference from the inbox.",
      true,
    );
    return;
  }

  const decision = document.getElementById("p_decision").value;
  const amount = parseFloat(document.getElementById("p_approved_amount").value);
  const remarks = document.getElementById("p_remarks").value;

  if (decision === "Rejected" && !remarks.trim()) {
    showToast(
      "A clear ruling reason must be entered in the remarks for all rejected items.",
      true,
    );
    return;
  }

  const logEntry = {
    timestamp: new Date().toLocaleString(),
    reqId: targetId,
    remarks: remarks || "Approved without optional remarks.",
    result: decision,
    amount: amount,
  };

  db.executiveLogs.push(logEntry);

  db.pendingPayments = db.pendingPayments.filter((p) => p.id !== targetId);

  saveSystemDatabase();
  renderAllComponents();
  clearPaymentApprovalSelection();
  loadPresidentialQueue();

  if (decision === "Approved") {
    showCustomModal(
      "Executive Clearance Appended",
      `Payment Reference ${targetId} verified. Approved amount ₱${amount.toFixed(2)} has been permanently saved to disbursement logs.`,
    );
  } else {
    showCustomModal(
      "Executive Rejection Logged",
      `Deficiency flagged. Reference ${targetId} returned to Treasurer's revision queue with notes: "${remarks}"`,
    );
  }
  showToast("Presidential decision saved.", false);
}

// Backend-driven Payments Verification Queue

let presidentialQueueCache = [];

document.addEventListener("DOMContentLoaded", function () {
  loadPresidentialQueue();
});

async function loadPresidentialQueue() {
  try {
    const response = await fetch("/api/payments/presidential-queue/");
    const result = await response.json();

    if (result.success) {
      presidentialQueueCache = result.payments;
      renderPendingTable(presidentialQueueCache);
    } else {
      console.error("Queue Retrieval Error:", result.message);
    }
  } catch (error) {
    console.error("Failed to fetch executive data:", error);
  }
}

function renderPendingTable(payments) {
  const tbody = document.querySelector("#pendingPaymentsTable tbody");
  tbody.innerHTML = "";

  if (payments.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#757575;">No active entries found inside verification workspace.</td></tr>`;
    return;
  }

  payments.forEach((item) => {
    const row = document.createElement("tr");
    row.style.cursor = "pointer";
    row.innerHTML = `
      <td><strong>${item.reference_code}</strong></td>
      <td>${item.member_name}</td>
      <td>₱${item.amount_paid.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
      <td><span class="badge badge-info">${item.payment_method}</span></td>
      <td>
        <button class="btn-brand btn-brand-primary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="selectPaymentRow(event, ${item.id})">
          Audit Entry
        </button>
      </td>
    `;
    row.addEventListener("click", () => populateDecisionDesk(item));
    tbody.appendChild(row);
  });
}

function populateDecisionDesk(item) {
  document.getElementById("selectedPaymentHeader").innerText =
    `Inspecting Ref: ${item.reference_code} | ${item.member_name}`;

  document.getElementById("pReadName").innerText = item.member_name;
  document.getElementById("pReadEmpId").innerText = item.employee_id;
  document.getElementById("pReadDept").innerText = item.department;
  document.getElementById("pReadStatus").innerText = item.membership_status;
  document.getElementById("pReadContact").innerText = item.contact_info;
  document.getElementById("pReadCovered").innerText = item.covered_period;
  document.getElementById("pReadExpected").innerText =
    `₱${(item.expected || item.amount_paid).toFixed(2)}`;
  document.getElementById("pReadMethod").innerText = item.payment_method;
  document.getElementById("pReadRef").innerText = item.reference_code;
  document.getElementById("pReadEncoder").innerText = item.encoder_name;

  document.getElementById("pApprovedMembershipTypeText").innerText =
    item.membership_type;
  document.getElementById("pApprovedMembershipRefText").innerText =
    item.membership_ref;
  document.getElementById("pApprovedMembershipMonthText").innerText =
    item.membership_month;
  document.getElementById("pApprovedMembershipAmountText").innerText =
    `₱${item.membership_amount.toFixed(2)}`;

  // Auditor summary (from backend payload)
  document.getElementById("pAuditByText").innerText =
    item?.auditorName && String(item.auditorName).trim()
      ? item.auditorName
      : "—";

  document.getElementById("pAuditDateText").innerText =
    item?.auditorDate && String(item.auditorDate).trim()
      ? item.auditorDate
      : "—";

  document.getElementById("pAuditEvidenceText").innerText = formatAuditEvidence(
    item?.auditorEvidence,
  );

  document.getElementById("pAuditRemarksText").innerText = formatAuditRemarks(
    item?.auditorRemarks,
  );

  document.getElementById("p_target_id").value = item.id;
  document.getElementById("p_approved_amount").value =
    item.amount_paid.toFixed(2);

  renderTimeline(item.timeline);
}

function selectPaymentRow(event, id) {
  event.stopPropagation();
  const targetItem = presidentialQueueCache.find((x) => x.id === id);
  if (targetItem) populateDecisionDesk(targetItem);
}

function renderTimeline(timelineArray) {
  const tbody = document.querySelector("#pTimelineTable tbody");
  // president_dashboard.html currently has the timeline block commented out.
  // Prevent runtime crashes so desk population & submission still work.
  if (!tbody) {
    return;
  }

  tbody.innerHTML = "";

  if (!timelineArray || timelineArray.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #757575">No history tracking points bound.</td></tr>`;
    return;
  }

  timelineArray.forEach((log) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><small>${log.timestamp}</small></td>
      <td><span class="badge">${log.role}</span></td>
      <td>${log.user}</td>
      <td><strong>${log.action}</strong></td>
      <td><span style="font-size:0.85rem; color:#555;">${log.notes}</span></td>
    `;
    tbody.appendChild(row);
  });
}

function handleDecisionChange(selectId, remarksId) {
  const decisionElement = document.getElementById(selectId);
  const remarksField = document.getElementById(remarksId);
  const labelField = document.getElementById(remarksId + "_label");

  if (decisionElement.value === "Rejected") {
    remarksField.setAttribute("required", "true");
    labelField.innerHTML = `Decision Remarks & Directives <span style="color:#d32f2f;">(Mandatory for Rejections)</span>`;
  } else {
    remarksField.removeAttribute("required");
    labelField.innerHTML = `Decision Remarks & Directives (Optional Override)`;
  }
}

function clearPaymentApprovalSelection() {
  document.getElementById("paymentApprovalForm").reset();
  document.getElementById("p_target_id").value = "";
  document.getElementById("selectedPaymentHeader").innerText =
    "No item selected";

  const selectors = [
    "#pReadName",
    "#pReadEmpId",
    "#pReadDept",
    "#pReadStatus",
    "#pReadContact",
    "#pReadCovered",
    "#pReadExpected",
    "#pReadMethod",
    "#pReadRef",
    "#pReadEncoder",
    "#pApprovedMembershipTypeText",
    "#pApprovedMembershipRefText",
    "#pApprovedMembershipMonthText",
    "#pApprovedMembershipAmountText",
    "#pAuditByText",
    "#pAuditDateText",
    "#pAuditEvidenceText",
    "#pAuditRemarksText",
  ];
  selectors.forEach((sel) => {
    const element = document.querySelector(sel);
    if (element) element.innerText = "—";
  });

  document.querySelector("#pTimelineTable tbody").innerHTML = `
    <tr><td colspan="5" style="text-align: center; color: #757575">No tracking logs compiled. Select a transaction to generate path timelines.</td></tr>
  `;
}

async function submitPresidentialPaymentDecision(event) {
  event.preventDefault();

  const targetId = document.getElementById("p_target_id").value;
  const decision = document.getElementById("p_decision").value;
  const remarks = document.getElementById("p_remarks").value;

  if (!targetId) {
    alert(
      "Please pick an active entry package from the ledger list layout beforehand.",
    );
    return;
  }

  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

  const payload = {
    target_id: targetId,
    decision: decision,
    remarks: remarks,
  };

  try {
    const response = await fetch("/api/payments/presidential-decision/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(payload),
    });

    const result = await response.json();

    if (result.success) {
      alert(result.message);
      clearPaymentApprovalSelection();
      loadPresidentialQueue();
    } else {
      alert("Execution Error: " + result.message);
    }
  } catch (error) {
    console.error("Transmission layout communication interruption: ", error);
    alert("Critical failure submitting transaction ruling updates.");
  }
}
