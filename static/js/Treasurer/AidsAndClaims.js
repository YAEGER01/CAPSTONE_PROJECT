// AidsAndClaims.js - Handles Medical Aid and Death Aid request/claim submission

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  return res.json();
}

async function apiAddMedicalAid(formData) {
  return fetchJson("/api/treasurer/medical-aid/add/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: formData,
  });
}

async function apiListMedicalAids() {
  return fetchJson("/api/treasurer/medical-aids/list/", {
    credentials: "same-origin",
  });
}

// ---------------- Death Aid APIs (Claims) ----------------
async function apiAddDeathAid(formData) {
  return fetchJson("/api/treasurer/death-aid/add/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: formData,
  });
}

async function apiListDeathAids() {
  return fetchJson("/api/treasurer/death-aids/list/", {
    credentials: "same-origin",
  });
}

function renderMedicalTableFromApi(medicalAids) {
  const tbody = document.querySelector("#medicalTable tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  if (!Array.isArray(medicalAids) || medicalAids.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="4" style="text-align:center;color:#757575;">No medical aid requests found</td></tr>';
    return;
  }

  medicalAids.forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:600;color:#1b5e20;">${m.id}</td>
      <td>${m.name}</td>
      <td>${m.reason} <br><span style="font-size:0.75rem;color:#757575;">At: ${m.hospital} (Bill: ₱${m.bill})</span></td>
      <td style="font-weight:600;">${formatCurrencyPHP(m.reqAmount)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function formatCurrencyPHP(num) {
  const n = Number(num || 0);
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
  }).format(n);
}

async function bootMedicalAidTable() {
  initMedicalMultiUpload();
  try {
    const data = await apiListMedicalAids();
    if (!data || !data.ok) return;
    renderMedicalTableFromApi(data.medical_aids || []);
  } catch (e) {
    console.error(e);
  }
}

// Load once DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootMedicalAidTable);
} else {
  bootMedicalAidTable();
}

// ---------- Multi-file management for Medical Aid ----------
let medFiles = [];

function initMedicalMultiUpload() {
  var input = document.getElementById("med_photo_files");
  var list = document.getElementById("med_file_list");
  if (!input || !list || input._medInit) return;
  input._medInit = true;

  input.addEventListener("change", function () {
    for (var fi = 0; fi < this.files.length; fi++) {
      var file = this.files[fi];
      var dup = false;
      for (var di = 0; di < medFiles.length; di++) {
        if (
          medFiles[di].name === file.name &&
          medFiles[di].size === file.size
        ) {
          dup = true;
          break;
        }
      }
      if (!dup) medFiles.push(file);
    }
    this.value = "";
    renderMedFileList();
  });
}

function renderMedFileList() {
  var list = document.getElementById("med_file_list");
  if (!list) return;
  list.innerHTML = "";
  var badge = list.parentElement
    ? list.parentElement.querySelector(".req-badge")
    : null;
  if (medFiles.length > 0) {
    if (badge) {
      badge.textContent = "✓ Attached";
      badge.style.color = "#2e7d32";
      badge.style.background = "rgba(46,125,50,0.1)";
    }
  } else {
    if (badge) {
      badge.textContent = "Required";
      badge.style.color = "#e53935";
      badge.style.background = "rgba(229,57,53,0.1)";
    }
  }
  for (var fi = 0; fi < medFiles.length; fi++) {
    var file = medFiles[fi];
    var div = document.createElement("div");
    div.style.cssText =
      "display:flex;align-items:center;gap:8px;padding:4px 8px;margin-bottom:4px;background:#f5f5f5;border-radius:6px;font-size:0.85rem";
    var preview = document.createElement("span");
    if (file.type.startsWith("image/")) {
      var img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      img.style.cssText =
        "width:36px;height:36px;object-fit:cover;border-radius:4px";
      var imgRef = img;
      img.onload = function () {
        URL.revokeObjectURL(imgRef.src);
      };
      preview.appendChild(img);
    } else {
      var icon = document.createElement("i");
      icon.className =
        file.type === "application/pdf"
          ? "fa-solid fa-file-pdf"
          : "fa-solid fa-file-word";
      icon.style.cssText = "font-size:1.3rem;color:#1565c0";
      preview.appendChild(icon);
    }
    div.appendChild(preview);
    var name = document.createElement("span");
    name.style.cssText =
      "flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    name.textContent = file.name;
    div.appendChild(name);
    var size = document.createElement("span");
    size.style.cssText = "color:#757575;font-size:0.75rem;white-space:nowrap";
    size.textContent = (file.size / 1024).toFixed(1) + " KB";
    div.appendChild(size);
    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.innerHTML = "&times;";
    removeBtn.style.cssText =
      "background:none;border:none;font-size:1.2rem;cursor:pointer;color:#e53935;padding:0 4px;line-height:1";
    removeBtn.title = "Remove file";
    (function (idx) {
      removeBtn.addEventListener("click", function () {
        medFiles.splice(idx, 1);
        renderMedFileList();
      });
    })(fi);
    div.appendChild(removeBtn);
    list.appendChild(div);
  }
}

function handleMedicalSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  if (medFiles.length === 0) {
    showToast("At least one supporting document is required.", true);
    return;
  }
  medFiles.forEach((f) => formData.append("med_photo_files", f));

  apiAddMedicalAid(formData)
    .then((data) => {
      if (!data.ok) {
        showToast(data.error || "Failed to submit medical aid request.", true);
        return null;
      }
      return apiListMedicalAids();
    })
    .then((data) => {
      if (!data) return;
      if (!data.ok) {
        showToast(data.error || "Medical Aid table refresh failed.", true);
        return;
      }
      renderMedicalTableFromApi(data.medical_aids || []);
      showToast("Medical Aid request submitted successfully.", false);
      form.reset();
      medFiles = [];
      renderMedFileList();
    })
    .catch((err) => {
      console.error(err);
      showToast("Network error while submitting.", true);
    });
}

// Expose handler globally for inline form attribute
function renderDeathTableFromApi(deathAids, tableId) {
  var tbody = document.querySelector("#" + tableId + " tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  if (!Array.isArray(deathAids) || deathAids.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" style="text-align:center;color:#757575;">No death aid claims found</td></tr>';
    return;
  }

  deathAids.forEach(function (d) {
    var badgeStyle = "badge-yellow";
    if (d.status === "Released") badgeStyle = "badge-green";
    if (d.status === "Rejection Dispatched") badgeStyle = "badge-red";

    var isMember = d.is_member_deceased === true;
    var scenarioBadge = isMember
      ? '<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">Member Deceased</span>'
      : '<span style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600;">Dependent Deceased</span>';

    var rawId = String(d.id || "")
      .replace("DTH-", "")
      .replace("death-", "");
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td style="font-weight:600;color:#1b5e20;">' +
      d.id +
      "</td>" +
      "<td>" +
      d.claimant +
      ' <br><span style="font-size:0.75rem;color:#757575;">Member: ' +
      d.name +
      "</span></td>" +
      "<td>" +
      scenarioBadge +
      ' <br><span style="font-size:0.85rem;">' +
      d.deceased +
      '</span> <br><span style="font-size:0.75rem;color:#757575;">' +
      (isMember ? "" : "Relationship: " + d.relationship) +
      "</span></td>" +
      '<td style="font-weight:600;">' +
      formatCurrencyPHP(d.benefit_amount) +
      "</td>" +
      "<td>" +
      (d.bill_amount ? formatCurrencyPHP(d.bill_amount) : "—") +
      "</td>" +
      '<td><span class="badge-zero ' +
      badgeStyle +
      '">' +
      d.status +
      "</span></td>";
    tbody.appendChild(tr);
  });
}

// ---------- Death Aid Scenario & Form ----------
let deathFiles = [];
const IMMEDIATE_RELATIONS = [
  "spouse",
  "husband",
  "wife",
  "parent",
  "child",
  "father",
  "mother",
  "son",
  "daughter",
  "brother",
  "sister",
];

function openDeathAidScenarioPicker() {
  // Reset any in-progress form first
  var formArea = document.getElementById("deathAidFormArea");
  if (formArea && formArea.style.display !== "none") {
    resetDeathAidForm();
  }
  Swal.fire({
    title: "Who is the deceased person?",
    html: [
      '<div style="display:flex;flex-direction:column;gap:12px;margin-top:16px">',
      '<button type="button" class="btn-brand btn-brand-primary" id="swl-death-member" style="width:100%;padding:14px;font-size:1.05rem;border-radius:30px">The Member (Policyholder)</button>',
      '<button type="button" class="btn-brand btn-brand-secondary" id="swl-death-dependent" style="width:100%;padding:14px;font-size:1.05rem;border-radius:30px">A Dependent (Spouse/Child/Parent/etc.)</button>',
      '<button type="button" class="btn-brand" id="swl-death-none" style="width:100%;padding:14px;font-size:1rem;background:#f5f5f5;color:#757575;border-radius:30px">None — Return to Dashboard</button>',
      "</div>",
    ].join(""),
    showConfirmButton: false,
    showCloseButton: true,
    customClass: { popup: "swal-rounded" },
    didOpen: function () {
      document.getElementById("swl-death-member").onclick = function () {
        Swal.close();
        setTimeout(function () {
          pickDeathMember();
        }, 100);
      };
      document.getElementById("swl-death-dependent").onclick = function () {
        Swal.close();
        setTimeout(function () {
          showDeathForm("dependent");
        }, 100);
      };
      document.getElementById("swl-death-none").onclick = function () {
        Swal.close();
        setTimeout(function () {
          setActiveModule("dashboard-overview");
        }, 100);
      };
    },
  });
}

function pickDeathMember() {
  var memberOptions = {};
  if (typeof db !== "undefined" && Array.isArray(db.members)) {
    db.members.forEach(function (m) {
      memberOptions[m.id] = m.name + " (" + m.id + ")";
    });
  }
  Swal.fire({
    title: "Select the Deceased Member",
    input: "select",
    inputOptions: memberOptions,
    inputPlaceholder: "-- Choose Member --",
    showCancelButton: true,
    confirmButtonText: "Continue",
    confirmButtonColor: "#1b5e20",
    customClass: { popup: "swal-rounded" },
    preConfirm: function (val) {
      if (!val) {
        Swal.showValidationMessage("Please select a member");
      }
      return val;
    },
  }).then(function (r) {
    if (r.isConfirmed) showDeathForm("member", r.value);
  });
}

function showDeathForm(scenario, memberId) {
  document.getElementById("deathAidScenarioArea").style.display = "none";
  document.getElementById("deathAidFormArea").style.display = "block";

  document.getElementById("death_scenario").value = scenario;

  if (scenario === "member") {
    document.getElementById("deathCard1Member").style.display = "block";
    document.getElementById("deathCard1Dependent").style.display = "none";
    document.getElementById("deathTableMember").style.display = "";
    document.getElementById("deathTableDependent").style.display = "none";
    var member = null;
    if (typeof db !== "undefined" && Array.isArray(db.members)) {
      for (var i = 0; i < db.members.length; i++) {
        if (String(db.members[i].id) === String(memberId)) {
          member = db.members[i];
          break;
        }
      }
    }
    if (member) {
      document.getElementById("death_member_name_display").textContent =
        member.name + " (" + member.id + ")";
      var decInput = document.getElementById("death_deceased");
      if (decInput) decInput.value = member.name;
    }
    document
      .getElementById("death_scenario")
      .setAttribute("data-member-id", memberId || "");
  } else {
    document.getElementById("deathCard1Member").style.display = "none";
    document.getElementById("deathCard1Dependent").style.display = "block";
    document.getElementById("deathTableMember").style.display = "none";
    document.getElementById("deathTableDependent").style.display = "";
    var sel = document.getElementById("death_member_select");
    if (sel) {
      sel.innerHTML = '<option value="">-- Choose Member ID --</option>';
      if (typeof db !== "undefined" && Array.isArray(db.members)) {
        for (var i = 0; i < db.members.length; i++) {
          var m = db.members[i];
          sel.innerHTML +=
            '<option value="' +
            m.id +
            '">' +
            m.name +
            " (" +
            m.id +
            ")" +
            "</option>";
        }
      }
    }
  }

  filterDeathTableByScenario(scenario);
  initDeathMultiUpload();
}

function filterDeathTableByScenario(scenario) {
  var all = (typeof db !== "undefined" && db.death_aids) || [];
  var filtered = all;
  var tableId = "deathTable";
  if (scenario === "member") {
    filtered = all.filter(function (d) {
      return d.is_member_deceased === true;
    });
    tableId = "deathTableMember";
  } else if (scenario === "dependent") {
    filtered = all.filter(function (d) {
      return d.is_member_deceased !== true;
    });
    tableId = "deathTableDependent";
  }
  renderDeathTableFromApi(filtered, tableId);
}

function resetDeathAidForm() {
  document.getElementById("deathForm").reset();
  deathFiles = [];
  var list = document.getElementById("death_file_list");
  if (list) {
    list.innerHTML = "";
    renderDeathFileList();
  }
  document.getElementById("deathAidFormArea").style.display = "none";
  document.getElementById("deathAidScenarioArea").style.display = "grid";
  refreshDeathAidTables();
  openDeathAidScenarioPicker();
}

function updateDeathRelOptions() {
  // Only operate on the visible card's elements
  var card1m = document.getElementById("deathCard1Member");
  var card1d = document.getElementById("deathCard1Dependent");
  var visibleCard = null;
  if (card1m && card1m.style.display !== "none") visibleCard = card1m;
  else if (card1d && card1d.style.display !== "none") visibleCard = card1d;
  if (!visibleCard) return;

  var group = visibleCard.querySelector(".death-rel-group");
  var relSelect = visibleCard.querySelector(".death-rel-select");
  var relText = visibleCard.querySelector(".death-rel-text");
  if (!group) return;

  var selectedGroup = group.value;

  if (relSelect) {
    relSelect.style.display = "none";
    relSelect.required = false;
  }
  if (relText) {
    relText.style.display = "none";
    relText.required = false;
  }

  if (selectedGroup === "immediate" && relSelect) {
    relSelect.style.display = "";
    relSelect.required = true;
    relSelect.innerHTML =
      '<option value="" disabled selected>Select relationship</option>';
    for (var j = 0; j < IMMEDIATE_RELATIONS.length; j++) {
      var r = IMMEDIATE_RELATIONS[j];
      relSelect.innerHTML +=
        '<option value="' +
        r +
        '">' +
        r.charAt(0).toUpperCase() +
        r.slice(1) +
        "</option>";
    }
    if (relText) relText.value = "";
  } else if (selectedGroup === "extended" && relText) {
    relText.style.display = "";
    relText.required = true;
    if (relSelect) relSelect.value = "";
  }
}

const DEATH_REL_MAP = {
  spouse: "spouse",
  husband: "husband",
  wife: "wife",
  parent: "parent",
  child: "child",
  father: "father",
  mother: "mother",
  son: "son",
  daughter: "daughter",
  "full-blood brother": "full-blood brother",
  "full-blood sister": "full-blood sister",
  brother: "brother",
  sister: "sister",
};

// ---------- Multi-file management for Death Aid ----------
function initDeathMultiUpload() {
  var input = document.getElementById("death_photo_files");
  var list = document.getElementById("death_file_list");
  if (!input || !list || input._deathInit) return;
  input._deathInit = true;

  input.addEventListener("change", function () {
    for (var fi = 0; fi < this.files.length; fi++) {
      var file = this.files[fi];
      var dup = false;
      for (var di = 0; di < deathFiles.length; di++) {
        if (
          deathFiles[di].name === file.name &&
          deathFiles[di].size === file.size
        ) {
          dup = true;
          break;
        }
      }
      if (!dup) deathFiles.push(file);
    }
    this.value = "";
    renderDeathFileList();
  });
}

function renderDeathFileList() {
  var list = document.getElementById("death_file_list");
  if (!list) return;
  list.innerHTML = "";
  var badge = list.parentElement
    ? list.parentElement.querySelector(".req-badge")
    : null;
  if (deathFiles.length > 0) {
    if (badge) {
      badge.textContent = "✓ Attached";
      badge.style.color = "#2e7d32";
      badge.style.background = "rgba(46,125,50,0.1)";
    }
  } else {
    if (badge) {
      badge.textContent = "Required";
      badge.style.color = "#e53935";
      badge.style.background = "rgba(229,57,53,0.1)";
    }
  }
  for (var fi = 0; fi < deathFiles.length; fi++) {
    var file = deathFiles[fi];
    var div = document.createElement("div");
    div.style.cssText =
      "display:flex;align-items:center;gap:8px;padding:4px 8px;margin-bottom:4px;background:#f5f5f5;border-radius:6px;font-size:0.85rem";
    var preview = document.createElement("span");
    if (file.type.startsWith("image/")) {
      var img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      img.style.cssText =
        "width:36px;height:36px;object-fit:cover;border-radius:4px";
      img.onload = function () {
        URL.revokeObjectURL(img.src);
      };
      preview.appendChild(img);
    } else {
      var icon = document.createElement("i");
      icon.className =
        file.type === "application/pdf"
          ? "fa-solid fa-file-pdf"
          : "fa-solid fa-file-word";
      icon.style.cssText = "font-size:1.3rem;color:#1565c0";
      preview.appendChild(icon);
    }
    div.appendChild(preview);
    var name = document.createElement("span");
    name.style.cssText =
      "flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    name.textContent = file.name;
    div.appendChild(name);
    var size = document.createElement("span");
    size.style.cssText = "color:#757575;font-size:0.75rem;white-space:nowrap";
    size.textContent = (file.size / 1024).toFixed(1) + " KB";
    div.appendChild(size);
    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.innerHTML = "&times;";
    removeBtn.style.cssText =
      "background:none;border:none;font-size:1.2rem;cursor:pointer;color:#e53935;padding:0 4px;line-height:1";
    removeBtn.title = "Remove file";
    (function (idx) {
      removeBtn.addEventListener("click", function () {
        deathFiles.splice(idx, 1);
        renderDeathFileList();
      });
    })(fi);
    div.appendChild(removeBtn);
    list.appendChild(div);
  }
}

async function bootDeathAidTable() {
  try {
    var data = await apiListDeathAids();
    if (!data || !data.ok) return;
    window.db = window.db || {};
    window.db.death_aids = data.death_aids || [];
    renderDeathTableFromApi(window.db.death_aids, "deathTable");
  } catch (e) {
    console.error(e);
  }
}
function refreshDeathAidTables() {
  var all = (typeof db !== "undefined" && db.death_aids) || [];
  renderDeathTableFromApi(all, "deathTable");
  renderDeathTableFromApi(
    all.filter(function (d) {
      return d.is_member_deceased === true;
    }),
    "deathTableMember",
  );
  renderDeathTableFromApi(
    all.filter(function (d) {
      return d.is_member_deceased !== true;
    }),
    "deathTableDependent",
  );
}

function handleDeathSubmit(event) {
  event.preventDefault();
  var form = event.target;
  var formData = new FormData(form);

  var scenario = document.getElementById("death_scenario").value;
  var visibleCard = null;
  if (document.getElementById("deathCard1Member").style.display !== "none")
    visibleCard = document.getElementById("deathCard1Member");
  else if (
    document.getElementById("deathCard1Dependent").style.display !== "none"
  )
    visibleCard = document.getElementById("deathCard1Dependent");

  // Resolve member ID
  var memberId = "";
  if (scenario === "member") {
    memberId =
      document
        .getElementById("death_scenario")
        .getAttribute("data-member-id") || "";
  } else if (visibleCard) {
    var memberSelect = visibleCard.querySelector(
      "#death_member_select, select[id^='death_member']",
    );
    if (memberSelect) memberId = memberSelect.value;
  }
  if (!memberId) {
    showToast("Please select a member.", true);
    return;
  }

  // Resolve relationship value from 2-part dropdown
  var relGroup = visibleCard
    ? visibleCard.querySelector(".death-rel-group")
    : null;
  var relSelect = visibleCard
    ? visibleCard.querySelector(".death-rel-select")
    : null;
  var relText = visibleCard
    ? visibleCard.querySelector(".death-rel-text")
    : null;
  var relValue = "";
  if (relGroup && relGroup.value === "immediate" && relSelect) {
    relValue = relSelect.value;
  } else if (relGroup && relGroup.value === "extended" && relText) {
    relValue = relText.value.trim();
  }
  if (!relValue) {
    showToast("Please select or specify the relationship.", true);
    return;
  }

  // Override visible-card fields to avoid duplicate-named hidden inputs corrupting POST
  if (visibleCard) {
    var clmInput = visibleCard.querySelector("[name='death_claimant']");
    if (clmInput) formData.set("death_claimant", clmInput.value);
    var cntInput = visibleCard.querySelector("[name='death_contact']");
    if (cntInput) formData.set("death_contact", cntInput.value);
  }
  formData.append("death_member", memberId);
  formData.append("death_rel", relValue);
  var relGroupEl = visibleCard
    ? visibleCard.querySelector(".death-rel-group")
    : null;
  formData.append("death_rel_group", relGroupEl ? relGroupEl.value : "");

  var billInput = document.getElementById("death_bill");
  if (billInput && !billInput.value.trim()) {
    if (
      !confirm(
        "Bill amount is empty. Are you sure you want to record this death claim without a bill amount?",
      )
    ) {
      return;
    }
  }

  if (deathFiles.length === 0) {
    showToast(
      "At least one supporting document (Death Certificate or equivalent) is required.",
      true,
    );
    return;
  }
  for (var fi = 0; fi < deathFiles.length; fi++) {
    formData.append("death_photo_files", deathFiles[fi]);
  }

  apiAddDeathAid(formData)
    .then(function (data) {
      if (!data.ok) {
        showToast(data.error || "Failed to submit death aid claim.", true);
        return null;
      }
      return apiListDeathAids();
    })
    .then(function (data) {
      if (!data) return;
      if (!data.ok) {
        showToast(data.error || "Death Aid table refresh failed.", true);
        return;
      }
      window.db = window.db || {};
      window.db.death_aids = data.death_aids || [];
      refreshDeathAidTables();
      showToast("Death Aid claim submitted successfully.", false);
      form.reset();
      deathFiles = [];
      renderDeathFileList();
    })
    ["catch"](function (err) {
      console.error(err);
      showToast("Network error while submitting.", true);
    });
}

// Expose functions globally
window.updateDeathRelOptions = updateDeathRelOptions;
window.resetDeathAidForm = resetDeathAidForm;
window.openDeathAidScenarioPicker = openDeathAidScenarioPicker;
window.showDeathForm = showDeathForm;

// Ensure death table loads on page open
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootDeathAidTable);
} else {
  bootDeathAidTable();
}

// Expose handlers globally for inline form attribute
window.handleMedicalSubmit = handleMedicalSubmit;
window.handleDeathSubmit = handleDeathSubmit;
