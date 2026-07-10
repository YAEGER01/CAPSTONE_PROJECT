// AidsAndClaims.js - Handles Medical Aid and Death Aid request/claim submission

var medSearchActiveIndex = -1;

function formatPhone(num) {
  if (!num) return "";
  var cleaned = num.replace(/[^\d]/g, "");
  if (cleaned.length === 11) {
    return cleaned.replace(/(\d{4})(\d{3})(\d{4})/, "$1 $2 $3");
  }
  if (cleaned.length === 7) {
    return cleaned.replace(/(\d{3})(\d{4})/, "$1-$2");
  }
  var match = num.match(/^(\d{3,4})[\s-]?(\d{3})[\s-]?(\d{4})$/);
  if (match) return "(" + match[1] + ") " + match[2] + "-" + match[3];
  return num;
}

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
      '<tr><td colspan="3" style="text-align:center;color:#757575;">No medical aid requests found</td></tr>';
    return;
  }

  medicalAids.forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
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

function toggleMedHospitalDrawer() {
  var body = document.getElementById("medHospitalDrawerBody");
  var chevron = document.getElementById("medHospitalChevron");
  if (!body || !chevron) return;
  var isOpen = body.style.maxHeight && body.style.maxHeight !== "0px";
  if (isOpen) {
    body.style.maxHeight = "0px";
    chevron.style.transform = "rotate(0deg)";
  } else {
    body.style.maxHeight = body.scrollHeight + "px";
    chevron.style.transform = "rotate(90deg)";
  }
}

function populateMedMemberSelect() {
  var sel = document.getElementById("med_member");
  if (!sel) return;
  sel.innerHTML = '<option value="">Select Associated Member</option>';
  if (typeof db !== "undefined" && Array.isArray(db.members)) {
    for (var i = 0; i < db.members.length; i++) {
      var m = db.members[i];
      var opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.name + " (" + (m.facultyId || m.id) + ")";
      opt.setAttribute("data-contact", m.contact || "");
      opt.setAttribute("data-status", m.status || "");
      sel.appendChild(opt);
    }
  }
}

function filterMedMembers(query) {
  var sel = document.getElementById("med_member");
  var results = document.getElementById("med_member_results");
  if (!sel || !results) return;
  medSearchActiveIndex = -1;
  var q = query.trim();
  if (!q) {
    results.style.display = "none";
    sel.style.display = "";
    return;
  }
  sel.style.display = "none";
  var ql = q.toLowerCase();
  var html = "";
  var count = 0;
  for (var i = 0; i < sel.options.length; i++) {
    var opt = sel.options[i];
    if (!opt.value) continue;
    if (opt.textContent.toLowerCase().includes(ql)) {
      var val = opt.value;
      var label = opt.textContent;
      html += '<div class="med-result-row" data-value="' + val + '" onclick="pickMedMember(\'' + val + '\')" style="display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid #f0f0f0;font-size:0.85rem;cursor:pointer;" onmouseover="this.style.background=\'#f5f5f5\'" onmouseout="this.style.background=\'\'">'
        + '<span>' + label + '</span>'
        + '<span class="med-pick-badge" onclick="event.stopPropagation();pickMedMember(\'' + val + '\')" style="display:inline-flex;align-items:center;gap:4px;padding:4px 14px;background:rgba(76,175,80,0.15);color:#2e7d32;border:1px solid rgba(76,175,80,0.3);border-radius:20px;font-size:0.72rem;font-weight:600;cursor:pointer;">Select &#10003;</span>'
        + '</div>';
      count++;
    }
  }
  if (count === 0) {
    html = '<div style="padding:8px 12px;color:#999;font-size:0.85rem;">No members found</div>';
  }
  results.innerHTML = html;
  results.style.display = "block";
}

function handleMedSearchKeydown(e) {
  var results = document.getElementById("med_member_results");
  if (!results || results.style.display !== "block") return;
  var items = results.querySelectorAll(".med-result-row");
  if (!items.length) {
    if (e.key === "Enter") { e.preventDefault(); }
    return;
  }
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      items[medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0].classList.remove("med-search-active");
      medSearchActiveIndex = Math.min(medSearchActiveIndex + 1, items.length - 1);
      items[medSearchActiveIndex].classList.add("med-search-active");
      items[medSearchActiveIndex].scrollIntoView({ block: "nearest" });
      break;
    case "Tab":
      e.preventDefault();
      if (e.shiftKey) {
        items[medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0].classList.remove("med-search-active");
        medSearchActiveIndex = Math.max(medSearchActiveIndex - 1, 0);
      } else {
        items[medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0].classList.remove("med-search-active");
        medSearchActiveIndex = Math.min(medSearchActiveIndex + 1, items.length - 1);
      }
      items[medSearchActiveIndex].classList.add("med-search-active");
      items[medSearchActiveIndex].scrollIntoView({ block: "nearest" });
      break;
    case "ArrowUp":
      e.preventDefault();
      items[medSearchActiveIndex >= 0 ? medSearchActiveIndex : 0].classList.remove("med-search-active");
      medSearchActiveIndex = Math.max(medSearchActiveIndex - 1, 0);
      items[medSearchActiveIndex].classList.add("med-search-active");
      items[medSearchActiveIndex].scrollIntoView({ block: "nearest" });
      break;
    case "Enter":
      e.preventDefault();
      if (medSearchActiveIndex >= 0 && medSearchActiveIndex < items.length) {
        pickMedMember(items[medSearchActiveIndex].getAttribute("data-value"));
      } else {
        var first = items[0];
        if (first) pickMedMember(first.getAttribute("data-value"));
      }
      break;
    case "Escape":
      document.getElementById("med_member_search").blur();
      hideMedResults();
      break;
  }
}

function pickMedMember(val) {
  var sel = document.getElementById("med_member");
  var searchInput = document.getElementById("med_member_search");
  var results = document.getElementById("med_member_results");
  if (!sel || !searchInput || !results) return;
  sel.value = val;
  var idx = sel.selectedIndex;
  if (idx > -1) searchInput.value = sel.options[idx].textContent;
  results.style.display = "none";
  sel.style.display = "";
  updateMedMemberInfo();
}

function hideMedResults() {
  medSearchActiveIndex = -1;
  var results = document.getElementById("med_member_results");
  var sel = document.getElementById("med_member");
  var searchInput = document.getElementById("med_member_search");
  if (results) results.style.display = "none";
  if (sel) sel.style.display = "";
  if (searchInput && !searchInput.value.trim()) {
    sel.value = "";
    var info = document.getElementById("med_member_info");
    if (info) info.style.display = "none";
  }
}

function onMedMemberSelect(sel) {
  var searchInput = document.getElementById("med_member_search");
  if (searchInput && sel.selectedIndex > -1 && sel.value) {
    searchInput.value = sel.options[sel.selectedIndex].textContent;
  }
  updateMedMemberInfo();
}

function updateMedMemberInfo() {
  var sel = document.getElementById("med_member");
  var info = document.getElementById("med_member_info");
  var nameEl = document.getElementById("med_member_info_name");
  var contactEl = document.getElementById("med_member_info_contact");
  var statusEl = document.getElementById("med_member_info_status");
  if (!sel || !info || !nameEl || !contactEl || !statusEl) return;
  var idx = sel.selectedIndex;
  if (idx < 0 || !sel.value) { info.style.display = "none"; return; }
  var opt = sel.options[idx];
  nameEl.textContent = opt.textContent;
  var searchInput = document.getElementById("med_member_search");
  if (searchInput) searchInput.value = opt.textContent;
  var contactVal = opt.getAttribute("data-contact") || "";
  contactEl.textContent = "Contact: " + (formatPhone(contactVal) || "N/A");
  var memberStatus = opt.getAttribute("data-status") || "";
  if (memberStatus) {
    statusEl.innerHTML = "Status: <span style='color:" + (memberStatus.toLowerCase() === "active" ? "#2e7d32" : "#c62828") + ";font-weight:600;'>" + memberStatus + "</span>";
  } else {
    statusEl.innerHTML = "";
  }
  var year = new Date().getFullYear();
  var existing = (typeof db !== "undefined" && Array.isArray(db.medical_aids)) ? db.medical_aids : [];
  var found = false;
  for (var i = 0; i < existing.length; i++) {
    var d = existing[i];
    if (String(d.memberId) === String(sel.value.replace("M-", "")) && d.date && d.date.indexOf(String(year)) === 0) {
      found = true;
      break;
    }
  }
  if (found) {
    statusEl.innerHTML += '<br><span style="color:#c62828;">&#9888; Already filed a claim this year</span>';
  }
  info.style.display = "block";
}

function updateMedBillIndicator() {
  var billInput = document.getElementById("med_bill");
  var indicator = document.getElementById("med_bill_indicator");
  if (!billInput || !indicator) return;
  var val = parseFloat(billInput.value);
  var threshold = parseFloat(document.getElementById("med_aid_estimate").getAttribute("data-threshold") || "20000");
  if (!val || isNaN(val)) { indicator.innerHTML = ""; return; }
  if (val > threshold) {
    indicator.innerHTML = '<span style="color:#2e7d32;">&#10003; Bill meets the minimum threshold (₱' + threshold.toFixed(2) + ')</span>';
  } else {
    indicator.innerHTML = '<span style="color:#c62828;">&#9888; Bill must exceed ₱' + threshold.toFixed(2) + ' to qualify</span>';
  }
}

async function bootMedicalAidTable() {
  initMedicalMultiUpload();
  populateMedMemberSelect();
  try {
    const data = await apiListMedicalAids();
    if (!data || !data.ok) return;
    window.db = window.db || {};
    window.db.medical_aids = data.medical_aids || [];
    renderMedicalTableFromApi(data.medical_aids || []);
  } catch (e) {
    console.error(e);
  }
}

document.addEventListener("turbo:load", bootMedicalAidTable);

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
      var fp = document.getElementById("med_hospital_date");
      if (fp && fp._flatpickr) fp._flatpickr.clear();
      var searchInput = document.getElementById("med_member_search");
      if (searchInput) searchInput.value = "";
      var sel = document.getElementById("med_member");
      if (sel) sel.style.display = "";
      var results = document.getElementById("med_member_results");
      if (results) results.style.display = "none";
      var memberInfo = document.getElementById("med_member_info");
      if (memberInfo) memberInfo.style.display = "none";
      var billInd = document.getElementById("med_bill_indicator");
      if (billInd) billInd.innerHTML = "";
    })
    .catch((err) => {
      console.error(err);
      showToast("Network error while submitting.", true);
    });
}

// --- Death Table Filter ---
window.__deathFilterState = { status: [] };

function deathToggleFilter() {
  var card = document.getElementById("deathFilterCard");
  if (!card) return;
  var opening = card.style.display === "none";
  card.style.display = opening ? "block" : "none";
  if (opening) {
    deathFillFilters();
    var handler = function(e) {
      var btn = document.querySelector('[onclick="deathToggleFilter()"]');
      if (card.contains(e.target) || (btn && btn.contains(e.target))) return;
      document.removeEventListener("click", handler);
      card.style.display = "none";
      deathApplyFilter();
    };
    setTimeout(function() { document.addEventListener("click", handler); }, 0);
  }
}

function deathGetChecked(id) {
  var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]:checked"), vals = [];
  for (var i = 0; i < cbs.length; i++) { var v = cbs[i].value; if (v !== "") vals.push(v); }
  return vals;
}

function deathGetAllValues(id) {
  var cbs = document.querySelectorAll("#" + id + " input[type=checkbox]"), vals = [];
  for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") vals.push(cbs[i].value); }
  return vals;
}

function deathToggleAll(containerId, checked) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var cbs = container.querySelectorAll('input[type="checkbox"]');
  for (var i = 0; i < cbs.length; i++) { if (cbs[i].value !== "") cbs[i].checked = checked; }
  deathApplyFilter();
}

function deathSyncAll(containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var cbs = container.querySelectorAll('input[type="checkbox"]');
  var allBox = cbs.length > 0 ? cbs[0] : null;
  if (!allBox) return;
  var allChecked = true;
  for (var i = 1; i < cbs.length; i++) { if (!cbs[i].checked) { allChecked = false; break; } }
  allBox.checked = allChecked;
}

function deathApplyFilter() { refreshDeathAidTables(); }

function deathFillFilters() {
  var stats = {}, i, d, arr = (typeof db !== "undefined" && db.death_aids) || window.__deathAidsAll || [];
  for (i = 0; i < arr.length; i++) { d = arr[i]; if (d.status) stats[d.status] = 1; }
  var sk = Object.keys(stats).sort();
  var sc = document.getElementById("deathStatusCheckboxes");
  if (sc) {
    sc.innerHTML = '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="" checked onchange="deathToggleAll(\'deathStatusCheckboxes\', this.checked)"> <span style="font-weight:600;">All</span></label>';
    for (i = 0; i < sk.length; i++) sc.innerHTML += '<label style="display:flex;align-items:center;gap:6px;font-size:0.82rem;padding:3px 0;cursor:pointer;"><input type="checkbox" value="' + escapeHtml(sk[i]) + '" checked onchange="deathSyncAll(\'deathStatusCheckboxes\');deathApplyFilter()"> <span>' + escapeHtml(sk[i]) + '</span></label>';
  }
}

// Expose handler globally for inline form attribute
function renderDeathTableFromApi(deathAids, tableId) {
  var tbody = document.querySelector("#" + tableId + " tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  var stats = tableId === "deathTable" ? deathGetChecked("deathStatusCheckboxes") : [];
  if (tableId === "deathTable" && stats.length === 0) { stats = deathGetAllValues("deathStatusCheckboxes"); deathSyncAll("deathStatusCheckboxes"); }

  var arr = deathAids || [], flt = [], i;
  for (i = 0; i < arr.length; i++) {
    var d = arr[i];
    if (stats.length && stats.indexOf(d.status) === -1) continue;
    flt.push(d);
  }

  if (flt.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#757580;padding:30px;">No death aid claims match current filters.</td></tr>';
    return;
  }

  flt.forEach(function (d) {
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
  "husband",
  "father",
  "son",
  "full-blood brother",
  "brother",
  "wife",
  "mother",
  "daughter",
  "full-blood sister",
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
            memberOptions[m.id] = m.name;
    });
  }
  Swal.fire({
    title: "Select the Deceased Member",
    input: "select",
    inputOptions: memberOptions,
    inputPlaceholder: "Select Associated Member",
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
      sel.innerHTML = '<option value="">Select Associated Member</option>';
      if (typeof db !== "undefined" && Array.isArray(db.members)) {
        for (var i = 0; i < db.members.length; i++) {
          var m = db.members[i];
          sel.innerHTML +=
            '<option value="' +
            m.id +
            '">' +
            m.name +
            "</option>";
        }
      }
      sel.onchange = function() {
        var selectedId = this.value;
        var claimantInput = document.getElementById("death_claimant_dep");
        var contactInput = document.getElementById("death_contact_dep");
        if (!selectedId || !claimantInput || !contactInput) return;
        if (typeof db !== "undefined" && Array.isArray(db.members)) {
          for (var i = 0; i < db.members.length; i++) {
            if (db.members[i].id === selectedId) {
              claimantInput.value = db.members[i].name;
              contactInput.value = db.members[i].contact || "";
              break;
            }
          }
        }
      };
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
  husband: "husband",
  wife: "wife",
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

// Toggle collapsible Funeral & Interment drawer
function toggleFuneralDrawer() {
  var body = document.getElementById("funeralDrawerBody");
  var chevron = document.getElementById("funeralChevron");
  if (!body || !chevron) return;
  var isOpen = body.style.maxHeight && body.style.maxHeight !== "0px";
  if (isOpen) {
    body.style.maxHeight = "0px";
    chevron.style.transform = "rotate(0deg)";
  } else {
    body.style.maxHeight = body.scrollHeight + "px";
    chevron.style.transform = "rotate(90deg)";
  }
}
window.toggleFuneralDrawer = toggleFuneralDrawer;

// Expose functions globally
window.updateDeathRelOptions = updateDeathRelOptions;
window.resetDeathAidForm = resetDeathAidForm;
window.openDeathAidScenarioPicker = openDeathAidScenarioPicker;
window.showDeathForm = showDeathForm;

document.addEventListener("turbo:load", bootDeathAidTable);

// Expose handlers globally for inline form attribute
window.handleMedicalSubmit = handleMedicalSubmit;
window.handleDeathSubmit = handleDeathSubmit;
window.toggleMedHospitalDrawer = toggleMedHospitalDrawer;
window.filterMedMembers = filterMedMembers;
window.updateMedBillIndicator = updateMedBillIndicator;
window.onMedMemberSelect = onMedMemberSelect;
window.pickMedMember = pickMedMember;
window.hideMedResults = hideMedResults;
window.handleMedSearchKeydown = handleMedSearchKeydown;
