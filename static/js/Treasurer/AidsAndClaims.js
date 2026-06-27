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
  // Render initial data from DB (instead of dummy/localStorage seed)
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

function handleMedicalSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  apiAddMedicalAid(formData)
    .then((data) => {
      if (!data.ok) {
        showToast(data.error || "Failed to submit medical aid request.", true);
        return Promise.reject(new Error(data.error || "Submit failed"));
      }

      return apiListMedicalAids();
    })
    .then((data) => {
      if (!data.ok) {
        showToast(data.error || "Medical Aid table refresh failed.", true);
        return;
      }

      renderMedicalTableFromApi(data.medical_aids || []);
      showToast("Medical Aid request submitted successfully.", false);
      form.reset();
      const preview = document.getElementById("med_preview");
      if (preview) preview.style.display = "none";
    })
    .catch((err) => {
      console.error(err);
      showToast("Network error while submitting.", true);
    });
}

// Expose handler globally for inline form attribute
function renderDeathTableFromApi(deathAids) {
  const tbody = document.querySelector("#deathTable tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  if (!Array.isArray(deathAids) || deathAids.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:#757575;">No death aid claims found</td></tr>';
    return;
  }

  deathAids.forEach((d) => {
    let badgeStyle = "badge-yellow";
    if (d.status === "Released") badgeStyle = "badge-green";
    if (d.status === "Rejection Dispatched") badgeStyle = "badge-red";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:600;color:#1b5e20;">${d.id}</td>
      <td>${d.claimant} <br><span style="font-size:0.75rem;color:#757575;">Member: ${d.name}</span></td>
      <td>Deceased: ${d.deceased} <br><span style="font-size:0.75rem;color:#757575;">Relationship: ${d.relationship}</span></td>
      <td style="font-weight:600;">${formatCurrencyPHP(d.benefit_amount)}</td>
      <td><span class="badge-zero ${badgeStyle}">${d.status}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

async function bootDeathAidTable() {
  try {
    const data = await apiListDeathAids();
    if (!data || !data.ok) return;
    renderDeathTableFromApi(data.death_aids || []);
  } catch (e) {
    console.error(e);
  }
}

function handleDeathSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  apiAddDeathAid(formData)
    .then((data) => {
      if (!data.ok) {
        showToast(data.error || "Failed to submit death aid claim.", true);
        return Promise.reject(new Error(data.error || "Submit failed"));
      }

      return apiListDeathAids();
    })
    .then((data) => {
      if (!data.ok) {
        showToast(data.error || "Death Aid table refresh failed.", true);
        return;
      }

      renderDeathTableFromApi(data.death_aids || []);
      showToast("Death Aid claim submitted successfully.", false);
      form.reset();
      const preview = document.getElementById("death_preview");
      if (preview) preview.style.display = "none";
    })
    .catch((err) => {
      console.error(err);
      showToast("Network error while submitting.", true);
    });
}

// Ensure death table loads on page open
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootDeathAidTable);
} else {
  bootDeathAidTable();
}

// Expose handlers globally for inline form attribute
window.handleMedicalSubmit = handleMedicalSubmit;
window.handleDeathSubmit = handleDeathSubmit;
