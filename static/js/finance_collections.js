(function () {
  "use strict";

  var cachedDepartments = null;
  var deptFetchTime = 0;
  var DETAIL_CACHE_TTL = 5 * 60 * 1000;
  var currentAidType = "medical";
  var currentClaimsDeptId = "";
  var currentFundPage = 1;

  var moduleEl = document.querySelector(".fc-module");
  if (!moduleEl) return;

  function officerRole() {
    return (moduleEl.getAttribute("data-officer-role") || "treasurer").toLowerCase();
  }

  function fmtPeso(n) {
    return "\u20B1" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function escapeHtml(s) {
    if (typeof s !== "string") return s;
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* ---- Tab Switching ---- */
  function switchTab(tabName) {
    document.querySelectorAll(".fc-tab").forEach(function (t) {
      t.classList.toggle("active", t.getAttribute("data-tab") === tabName);
    });
    document.querySelectorAll(".fc-tab-content").forEach(function (c) {
      c.classList.toggle("active", c.id === "fc-tab-" + tabName);
    });
    if (tabName === "departments") loadDepartments();
    if (tabName === "fund-activity") loadFundActivity(1);
    if (tabName === "aids-claims") loadClaims();
  }

  document.querySelectorAll(".fc-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      switchTab(this.getAttribute("data-tab"));
    });
  });

  /* ---- Fund Activity ---- */
  function loadFundActivity(page) {
    currentFundPage = page;
    var container = document.getElementById("fc-timeline");
    container.innerHTML = '<div class="fc-loading">Loading fund activity...</div>';
    var paginationEl = document.getElementById("fc-timeline-pagination");

    fetchBalance();

    fetch("/api/finance-collections/fund-activity/?page=" + page, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { container.innerHTML = "<div class='fc-loading'>Failed to load.</div>"; return; }
        if (data.transactions.length === 0) {
          container.innerHTML = "<div class='fc-loading'>No transactions yet.</div>";
          paginationEl.innerHTML = "";
          return;
        }
        var html = "";
        data.transactions.forEach(function (tx, i) {
          var idx = (page - 1) * 20 + i + 1;
          var dirClass = tx.direction === "inflow" ? "inflow" : "outflow";
          var sign = tx.direction === "inflow" ? "+" : "-";
          html += '<div class="fc-tx-row">';
          html += '<span class="fc-tx-idx">' + idx + "</span>";
          html += '<span class="fc-tx-direction ' + dirClass + '">' + tx.direction + "</span>";
          html += '<span class="fc-tx-desc">' + escapeHtml(tx.description) + "</span>";
          html += '<span class="fc-tx-amount">' + sign + fmtPeso(tx.amount) + "</span>";
          html += '<span class="fc-tx-date">' + escapeHtml(tx.recorded_at.slice(0, 10)) + "</span>";
          if (tx.proofs && tx.proofs.length > 0) {
            html += '<div class="fc-tx-proofs">';
            tx.proofs.forEach(function (p) {
              html += '<a class="fc-tx-proof-link" href="' + escapeHtml(p.file_url) + '" target="_blank">' + escapeHtml(p.file_name) + "</a>";
            });
            html += "</div>";
          }
          html += "</div>";
        });
        container.innerHTML = html;

        var pagHtml = "";
        for (var p = 1; p <= data.total_pages; p++) {
          pagHtml += '<button class="fc-page-btn' + (p === page ? " active" : "") + '" data-page="' + p + '">' + p + "</button>";
        }
        paginationEl.innerHTML = pagHtml;
        paginationEl.querySelectorAll(".fc-page-btn").forEach(function (btn) {
          btn.addEventListener("click", function () { loadFundActivity(parseInt(this.getAttribute("data-page"), 10)); });
        });
      })
      .catch(function () { container.innerHTML = "<div class='fc-loading'>Error loading.</div>"; });
  }

  function fetchBalance() {
    fetch("/api/fund-balance/", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var el = document.getElementById("fc-balance-amount");
        if (el && typeof data.balance === "number") el.innerText = fmtPeso(data.balance);
      })
      .catch(function () {});
  }

  /* ---- Departments ---- */
  function loadDepartments() {
    var sidebar = document.getElementById("fc-dept-sidebar");
    if (cachedDepartments && Date.now() - deptFetchTime < DETAIL_CACHE_TTL) {
      renderDeptSidebar(cachedDepartments);
      return;
    }
    sidebar.innerHTML = '<div class="fc-loading">Loading departments...</div>';
    fetch("/api/finance-collections/departments/", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { sidebar.innerHTML = "<div class='fc-loading'>Failed to load.</div>"; return; }
        cachedDepartments = data.departments;
        deptFetchTime = Date.now();
        renderDeptSidebar(data.departments);
        populateDeptFilter(data.departments);
      })
      .catch(function () { sidebar.innerHTML = "<div class='fc-loading'>Error loading.</div>"; });
  }

  function renderDeptSidebar(departments) {
    var sidebar = document.getElementById("fc-dept-sidebar");
    if (departments.length === 0) { sidebar.innerHTML = "<div class='fc-loading'>No departments.</div>"; return; }
    var html = "";
    departments.forEach(function (d) {
      html += '<div class="fc-dept-item" data-dept-id="' + d.id + '">';
      html += escapeHtml(d.name);
      html += ' <span class="dept-count">' + (d.active_count || 0) + " active</span></div>";
    });
    sidebar.innerHTML = html;
    sidebar.querySelectorAll(".fc-dept-item").forEach(function (item) {
      item.addEventListener("click", function () {
        sidebar.querySelectorAll(".fc-dept-item").forEach(function (i) { i.classList.remove("active"); });
        this.classList.add("active");
        selectDept(parseInt(this.getAttribute("data-dept-id"), 10));
      });
    });
  }

  function populateDeptFilter(departments) {
    var sel = document.getElementById("fc-claims-dept-filter");
    if (!sel) return;
    sel.innerHTML = '<option value="">All Departments</option>';
    departments.forEach(function (d) {
      sel.innerHTML += '<option value="' + d.id + '">' + escapeHtml(d.name) + "</option>";
    });
  }

  function selectDept(deptId) {
    var detail = document.getElementById("fc-dept-detail");
    detail.innerHTML = '<div class="fc-loading">Loading department...</div>';
    fetch("/api/finance-collections/department/" + deptId + "/summary/", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { detail.innerHTML = "<div class='fc-loading'>Failed to load.</div>"; return; }
        var html = '<h3 style="margin-bottom:12px">' + escapeHtml(data.department.name) + "</h3>";
        if (data.members.length === 0) { html += "<p>No members in this department.</p>"; detail.innerHTML = html; return; }
        data.members.forEach(function (m) {
          var paid = m.dues.current_year.paid || 0;
          var missed = m.dues.current_year.missed || 0;
          var total = m.dues.current_year.total_months || 12;
          html += '<div class="fc-member-row" data-member-id="' + m.member_id + '">';
          html += '<span class="member-name">' + escapeHtml(m.full_name) + "</span>";
          html += '<span class="member-dues">Dues: ' + paid + "/" + total + " paid</span>";
          html += '<span class="member-claims">Claims: ' + (m.claims.medical.length + m.claims.death.length) + "</span>";
          html += "</div>";
          html += '<div class="fc-member-detail-panel" id="member-detail-' + m.member_id + '"></div>';
        });
        detail.innerHTML = html;
        detail.querySelectorAll(".fc-member-row").forEach(function (row) {
          row.addEventListener("click", function () {
            var mid = parseInt(this.getAttribute("data-member-id"), 10);
            toggleMemberDetail(mid);
          });
        });
      })
      .catch(function () { detail.innerHTML = "<div class='fc-loading'>Error loading.</div>"; });
  }

  function toggleMemberDetail(memberId) {
    var panel = document.getElementById("member-detail-" + memberId);
    if (!panel) return;
    if (panel.classList.contains("open")) {
      panel.classList.remove("open");
      panel.innerHTML = "";
      return;
    }
    document.querySelectorAll(".fc-member-detail-panel.open").forEach(function (p) { p.classList.remove("open"); p.innerHTML = ""; });
    panel.classList.add("open");
    loadMemberDetailYear(memberId, null, panel);
  }

  function loadMemberDetailYear(memberId, year, panel) {
    if (!panel) panel = document.getElementById("member-detail-" + memberId);
    if (!panel) return;
    panel.innerHTML = '<div class="fc-loading">Loading details...</div>';

    var url = "/api/finance-collections/member/" + memberId + "/collections/";
    if (year) url += "?year=" + year;

    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { panel.innerHTML = "<div class='fc-loading'>Failed to load.</div>"; return; }
        renderMemberDetail(panel, data);
      })
      .catch(function () { panel.innerHTML = "<div class='fc-loading'>Error loading.</div>"; });
  }

  function renderMemberDetail(panel, data) {
    var html = "";
    var member = data.member || {};
    var selectedYear = data.selected_year || new Date().getFullYear();
    var memberId = member.member_id;

    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">';
    html += '<div><strong>' + escapeHtml(member.full_name || "") + "</strong>";
    if (member.employee_id) html += '<span style="font-size:12px;color:#999;margin-left:8px">#' + escapeHtml(member.employee_id) + "</span>";
    html += "</div>";
    html += '<span style="font-size:12px;color:#666">' + escapeHtml(member.department || "") + "</span>";
    html += "</div>";

    var duesGrid = data.dues_grid || {};
    var yearData = duesGrid[selectedYear] || {};

    html += "<h4 style='font-size:13px;margin-bottom:8px;color:#333'>Monthly Dues</h4>";
    html += '<div style="border:1px solid #e0e0e0;border-radius:12px;padding:16px;background:#fff;margin-bottom:12px;">';

    html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">';
    html += '<button class="fc-year-nav prev" data-dir="-1" data-member-id="' + memberId + '" style="padding:4px 10px;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;font-size:13px;">◀</button>';
    html += '<span style="font-size:15px;font-weight:600;min-width:60px;text-align:center;">' + selectedYear + "</span>";
    html += '<button class="fc-year-nav next" data-dir="1" data-member-id="' + memberId + '" style="padding:4px 10px;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;font-size:13px;">▶</button>';
    html += "</div>";

    html += '<div class="fc-cal-heatmap" style="display:inline-block;">';
    var monthLabels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    html += '<div style="display:flex;gap:2px;margin-bottom:4px;">';
    html += '<div style="width:36px;"></div>';
    for (var mi = 0; mi < 12; mi++) {
      html += '<div style="width:24px;text-align:center;font-size:9px;color:#999;">' + monthLabels[mi] + "</div>";
    }
    html += "</div>";
    var paidStatuses = ["PAID", "Auditor Verified", "Approved"];
    html += '<div style="display:flex;gap:2px;align-items:center;margin-bottom:2px;">';
    html += '<div style="width:36px;font-size:11px;color:#666;text-align:right;padding-right:4px;">' + selectedYear + "</div>";
    for (var mi = 0; mi < 12; mi++) {
      var mKey = selectedYear + "-" + (mi + 1).toString().padStart(2, "0");
      var cell = yearData[mKey] || { status: "NONE" };
      var cls = "none";
      if (paidStatuses.indexOf(cell.status) !== -1) cls = "paid";
      else if (cell.status !== "NONE") cls = "missed";
      html += '<div class="fc-heat-cell ' + cls + '" title="' + escapeHtml(mKey) + ": " + escapeHtml(cell.status) + '" style="width:24px;height:24px;border-radius:4px;font-size:9px;display:flex;align-items:center;justify-content:center;cursor:default;"></div>';
    }
    html += "</div>";
    html += "</div>";
    html += '<div style="margin-top:8px;font-size:11px;display:flex;gap:12px;align-items:center;">';
    html += '<span>Legend:</span>';
    html += '<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:#c8e6c9;"></span> Paid';
    html += '<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:#ffcdd2;"></span> Missed';
    html += '<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:#f0f0f0;"></span> No Record';
    html += "</div>";

    html += "</div>";

    var contribs = data.contributions || [];
    var unpaidContribs = contribs.filter(function (c) { return c.paid < c.expected; });
    if (unpaidContribs.length > 0) {
      html += "<h4 style='font-size:13px;margin:12px 0 8px;color:#c62828;'>Unpaid Contributions</h4>";
      html += '<div style="border:1px solid #ffcdd2;border-radius:12px;padding:16px;background:#fff5f5;margin-bottom:12px;">';
      unpaidContribs.forEach(function (c) {
        var due = c.expected - c.paid;
        html += '<div class="fc-progress-wrap" style="margin-bottom:10px;">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;">';
        html += '<strong style="font-size:13px;">' + escapeHtml(c.aid_type.toUpperCase()) + "</strong>";
        html += '<span style="font-size:14px;font-weight:700;color:#c62828;">' + fmtPeso(due) + " due</span>";
        html += "</div>";
        html += '<div style="font-size:12px;color:#666;margin-top:4px;">Paid: ' + fmtPeso(c.paid) + " of " + fmtPeso(c.expected) + "</div>";
        html += '<div class="fc-progress-bar" style="margin-top:6px;"><div class="fc-progress-fill" style="width:' + (c.expected > 0 ? Math.round((c.paid / c.expected) * 100) : 0) + '%;background:#ef9a9a;"></div></div>';
        html += "</div>";
      });
      html += "</div>";
    }

    var claims = data.claims || {};
    var allClaims = (claims.medical || []).concat(claims.death || []);
    if (allClaims.length > 0) {
      html += "<h4 style='font-size:13px;margin:12px 0 8px'>Recent Claims</h4>";
      html += "<div style='display:flex;flex-wrap:wrap;gap:6px'>";
      allClaims.forEach(function (cl) {
        html += '<span class="fc-claim-badge" data-claim-id="' + cl.id + '" data-claim-type="' + (cl.hospital !== undefined ? "medical" : "death") + '" style="padding:4px 10px;background:#e8f5e9;border-radius:12px;font-size:11px;cursor:pointer">' + fmtPeso(cl.amount) + " (" + escapeHtml(cl.status) + ")</span>";
      });
      html += "</div>";
    }

    var history = data.payment_history || [];
    html += "<h4 style='font-size:13px;margin:12px 0 8px;color:#333;'>Payment History</h4>";
    html += '<div style="border:1px solid #e0e0e0;border-radius:12px;padding:16px;background:#fff;margin-bottom:12px;">';
    html += '<div style="display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap;" class="fc-history-filters">';
    var categories = [
      { key: "all", label: "All" },
      { key: "membership_fee", label: "Membership" },
      { key: "monthly_dues", label: "Dues" },
      { key: "aid", label: "Aids" },
      { key: "claim", label: "Claims" },
    ];
    categories.forEach(function (cat) {
      var active = cat.key === "all" ? ' style="background:#1a7a2e;color:#fff;border-color:#1a7a2e;"' : "";
      html += '<button class="fc-history-filter" data-filter="' + cat.key + '"' + active + ' style="padding:4px 12px;border:1px solid #ddd;border-radius:12px;background:#fff;cursor:pointer;font-size:11px;">' + cat.label + "</button>";
    });
    html += "</div>";
    html += '<div style="max-height:280px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;" class="fc-history-list">';
    if (history.length === 0) {
      html += '<div style="font-size:12px;color:#999;text-align:center;padding:20px;">No transactions found.</div>';
    } else {
      history.forEach(function (tx) {
        html += buildHistoryRow(tx);
      });
    }
    html += "</div>";
    html += "</div>";

    panel.innerHTML = html;

    panel.querySelectorAll(".fc-year-nav").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dir = parseInt(this.getAttribute("data-dir"), 10);
        var mid = parseInt(this.getAttribute("data-member-id"), 10);
        var newYear = selectedYear + dir;
        loadMemberDetailYear(mid, String(newYear), panel);
      });
    });
  }

  /* ---- Claims ---- */
  function loadClaims() {
    var container = document.getElementById("fc-claims-grid");
    container.innerHTML = '<div class="fc-loading">Loading claims...</div>';

    var url = "/api/finance-collections/departments/";
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (deptData) {
        if (!deptData.ok) { container.innerHTML = "<div class='fc-loading'>Failed to load.</div>"; return; }
        renderClaims(container, deptData.departments);
      })
      .catch(function () { container.innerHTML = "<div class='fc-loading'>Error loading.</div>"; });
  }

  function renderClaims(container, departments) {
    var filtered = departments;
    if (currentClaimsDeptId) {
      filtered = departments.filter(function (d) { return d.id === parseInt(currentClaimsDeptId, 10); });
    }
    if (filtered.length === 0) { container.innerHTML = "<div class='fc-loading'>No data for selected filter.</div>"; return; }

    container.innerHTML = '<div class="fc-loading">Loading claims...</div>';
    var allFetches = filtered.map(function (d) {
      return fetch("/api/finance-collections/department/" + d.id + "/summary/", { credentials: "same-origin" })
        .then(function (r) { return r.json(); });
    });
    Promise.all(allFetches).then(function (results) {
      var html = "";
      var processed = 0;
      var maxCards = 100;
      results.forEach(function (data) {
        if (!data.ok) return;
        data.members.forEach(function (m) {
          if (processed >= maxCards) return;
          var claims = currentAidType === "medical" ? m.claims.medical : m.claims.death;
          claims.forEach(function (cl) {
            if (processed >= maxCards) return;
            html += '<div class="fc-claim-card fc-claim-clickable" data-claim-id="' + cl.id + '" data-claim-type="' + currentAidType + '">';
            html += '<div class="claim-member">' + escapeHtml(m.full_name) + "</div>";
            html += '<div class="claim-detail">' + escapeHtml(cl.status) + " &middot; " + escapeHtml(data.department.name) + "</div>";
            html += '<div class="claim-amount">' + fmtPeso(cl.amount) + "</div>";
            html += "</div>";
            processed++;
          });
        });
      });
      container.innerHTML = html || "<div class='fc-loading'>No claims found.</div>";
    }).catch(function () {
      container.innerHTML = "<div class='fc-loading'>Error loading claims.</div>";
    });
  }

  /* ---- Claim Click / Badge Click -> Swal Modal ---- */
  document.getElementById("fc-dept-detail").addEventListener("click", function (e) {
    var badge = e.target.closest(".fc-claim-badge");
    if (!badge) return;
    var claimId = parseInt(badge.getAttribute("data-claim-id"), 10);
    var claimType = badge.getAttribute("data-claim-type");
    if (!claimId || !claimType) return;
    showClaimDetail(claimId, claimType);
  });

  document.getElementById("fc-claims-grid").addEventListener("click", function (e) {
    var card = e.target.closest(".fc-claim-clickable");
    if (!card) return;
    var claimId = parseInt(card.getAttribute("data-claim-id"), 10);
    var claimType = card.getAttribute("data-claim-type");
    if (!claimId || !claimType) return;
    showClaimDetail(claimId, claimType);
  });

  function showClaimDetail(claimId, claimType) {
    var url = "/api/finance-collections/" + (claimType === "medical" ? "medical-aid" : "death-aid") + "/" + claimId + "/detail/";
    showToast("Fetching claim details...", false);
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) {
          showToast(data.error || "Failed to load claim details.", true);
          return;
        }
        var c = data.claim;
        var html = "";
        if (claimType === "medical") {
          var payStatusBg = "#fff3e0"; var payStatusColor = "#e65100";
          if (c.payment_status === "Disbursed") { payStatusBg = "#e8f5e9"; payStatusColor = "#2e7d32"; }
          else if (c.payment_status === "Approved — Awaiting Disbursement") { payStatusBg = "#fff8e1"; payStatusColor = "#f57f17"; }
          html += "<table style='width:100%;border-collapse:collapse;font-size:14px'>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555;width:140px'>Member</td><td style='padding:6px 12px'>" + escapeHtml(c.member_name) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Payment Status</td><td style='padding:6px 12px'><span style='padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600;background:" + payStatusBg + ";color:" + payStatusColor + "'>" + escapeHtml(c.payment_status) + "</span></td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Request Date</td><td style='padding:6px 12px'>" + escapeHtml(c.request_date) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Hospital</td><td style='padding:6px 12px'>" + escapeHtml(c.hospital_name) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Hospital Bill</td><td style='padding:6px 12px'>" + fmtPeso(c.hospital_bill_amount) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Validated Amt</td><td style='padding:6px 12px'>" + fmtPeso(c.requested_amount) + "</td></tr>";
          if (c.disbursement_source) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Source</td><td style='padding:6px 12px'>" + escapeHtml(c.disbursement_source) + "</td></tr>";
          if (c.release_reference) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Release Ref</td><td style='padding:6px 12px'>" + escapeHtml(c.release_reference) + "</td></tr>";
          if (c.acknowledgement_reference) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Ack Ref</td><td style='padding:6px 12px'>" + escapeHtml(c.acknowledgement_reference) + "</td></tr>";
          if (c.president_decision) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Pres. Posting Decision</td><td style='padding:6px 12px'>" + escapeHtml(c.president_decision) + "</td></tr>";
          html += "</table>";
          if (c.fund_transactions && c.fund_transactions.length > 0) {
            html += "<h4 style='font-size:13px;margin:16px 0 8px;color:#333'>Disbursement Transactions</h4>";
            html += "<table style='width:100%;border-collapse:collapse;font-size:13px'>";
            html += "<tr style='background:#f5f5f5'><th style='padding:6px 8px;text-align:left;font-size:11px;color:#666'>Date</th><th style='padding:6px 8px;text-align:left;font-size:11px;color:#666'>Description</th><th style='padding:6px 8px;text-align:right;font-size:11px;color:#666'>Amount</th></tr>";
            var grandTotal = 0;
            c.fund_transactions.forEach(function (tx) {
              grandTotal += tx.amount;
              html += "<tr><td style='padding:4px 8px;font-size:12px'>" + escapeHtml((tx.recorded_at || "").slice(0, 10)) + "</td>";
              html += "<td style='padding:4px 8px;font-size:12px'>" + escapeHtml(tx.description) + "</td>";
              html += "<td style='padding:4px 8px;font-size:12px;text-align:right;font-weight:600'>" + fmtPeso(tx.amount) + "</td></tr>";
            });
            html += "<tr style='border-top:2px solid #1a7a2e'><td style='padding:6px 8px;font-weight:700;color:#1a7a2e' colspan='2'>Total Disbursed</td><td style='padding:6px 8px;font-weight:700;color:#1a7a2e;text-align:right'>" + fmtPeso(grandTotal) + "</td></tr>";
            html += "</table>";
          }
        } else {
          var payStatusBg = "#fff3e0"; var payStatusColor = "#e65100";
          if (c.payment_status === "Disbursed") { payStatusBg = "#e8f5e9"; payStatusColor = "#2e7d32"; }
          else if (c.payment_status === "Approved — Awaiting Disbursement") { payStatusBg = "#fff8e1"; payStatusColor = "#f57f17"; }
          html += "<table style='width:100%;border-collapse:collapse;font-size:14px'>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555;width:140px'>Member</td><td style='padding:6px 12px'>" + escapeHtml(c.member_name) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Payment Status</td><td style='padding:6px 12px'><span style='padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600;background:" + payStatusBg + ";color:" + payStatusColor + "'>" + escapeHtml(c.payment_status) + "</span></td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Claim Date</td><td style='padding:6px 12px'>" + escapeHtml(c.claim_date) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Beneficiary</td><td style='padding:6px 12px'>" + escapeHtml(c.claim_type === "Immediate Family" ? "Family of Member" : c.claim_type === "Member" ? "Member" : c.claim_type) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Deceased</td><td style='padding:6px 12px'>" + escapeHtml(c.deceased_name) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Relationship</td><td style='padding:6px 12px'>" + escapeHtml(c.relationship_to_member) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Funeral Location</td><td style='padding:6px 12px'>" + escapeHtml(c.funeral_location) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Interment Date</td><td style='padding:6px 12px'>" + escapeHtml(c.interment_date) + "</td></tr>";
          html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Total Paid</td><td style='padding:6px 12px;font-weight:700;color:#1a7a2e'>" + fmtPeso(c.total_paid) + "</td></tr>";
          if (c.bill_amount > 0) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Bill Amount</td><td style='padding:6px 12px'>" + fmtPeso(c.bill_amount) + "</td></tr>";
          if (c.disbursement_source) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Source</td><td style='padding:6px 12px'>" + escapeHtml(c.disbursement_source) + "</td></tr>";
          if (c.release_reference) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Release Ref</td><td style='padding:6px 12px'>" + escapeHtml(c.release_reference) + "</td></tr>";
          if (c.acknowledgement_reference) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Ack Ref</td><td style='padding:6px 12px'>" + escapeHtml(c.acknowledgement_reference) + "</td></tr>";
          if (c.president_decision) html += "<tr><td style='padding:6px 12px;font-weight:600;color:#555'>Pres. Posting Decision</td><td style='padding:6px 12px'>" + escapeHtml(c.president_decision) + "</td></tr>";
          html += "</table>";
          if (c.fund_transactions && c.fund_transactions.length > 0) {
            html += "<h4 style='font-size:13px;margin:16px 0 8px;color:#333'>Disbursement Transactions</h4>";
            html += "<table style='width:100%;border-collapse:collapse;font-size:13px'>";
            html += "<tr style='background:#f5f5f5'><th style='padding:6px 8px;text-align:left;font-size:11px;color:#666'>Date</th><th style='padding:6px 8px;text-align:left;font-size:11px;color:#666'>Description</th><th style='padding:6px 8px;text-align:right;font-size:11px;color:#666'>Amount</th></tr>";
            var grandTotal = 0;
            c.fund_transactions.forEach(function (tx) {
              grandTotal += tx.amount;
              html += "<tr><td style='padding:4px 8px;font-size:12px'>" + escapeHtml((tx.recorded_at || "").slice(0, 10)) + "</td>";
              html += "<td style='padding:4px 8px;font-size:12px'>" + escapeHtml(tx.description) + "</td>";
              html += "<td style='padding:4px 8px;font-size:12px;text-align:right;font-weight:600'>" + fmtPeso(tx.amount) + "</td></tr>";
            });
            html += "<tr style='border-top:2px solid #1a7a2e'><td style='padding:6px 8px;font-weight:700;color:#1a7a2e' colspan='2'>Total Disbursed</td><td style='padding:6px 8px;font-weight:700;color:#1a7a2e;text-align:right'>" + fmtPeso(grandTotal) + "</td></tr>";
            html += "</table>";
          }
        }
        Swal.fire({ title: (claimType === "medical" ? "Medical Aid" : "Death Aid") + " Details", html: html, confirmButtonText: "Close" });
      })
      .catch(function () {
        showToast("Failed to load claim details.", true);
      });
  }

  /* ---- Aids & Claims Tab filter buttons ---- */
  document.querySelectorAll(".fc-filter-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".fc-filter-btn").forEach(function (b) { b.classList.remove("active"); });
      this.classList.add("active");
      currentAidType = this.getAttribute("data-aid-type");
      loadClaims();
    });
  });

  var deptFilter = document.getElementById("fc-claims-dept-filter");
  if (deptFilter) {
    deptFilter.addEventListener("change", function () {
      currentClaimsDeptId = this.value;
      loadClaims();
    });
  }

  var recordBtn = document.getElementById("fc-record-transaction-btn");
  if (recordBtn) {
    recordBtn.addEventListener("click", function () {
      alert("Record Fund Transaction: feature coming soon.");
    });
  }

  document.addEventListener("turbo:load", function () {
    if (document.querySelector(".fc-module")) {
      loadFundActivity(1);
    }
  });

  if (document.querySelector(".fc-module")) {
    loadFundActivity(1);
  }

  function buildHistoryRow(tx) {
    var colorMap = {
      membership_fee: "#1565c0",
      monthly_dues: "#2e7d32",
      aid: "#e65100",
      claim: "#6a1b9a",
    };
    var dotColor = colorMap[tx.type] || "#999";
    var amtClass = tx.type === "claim" ? "color:#c62828;" : "color:#2e7d32;";
    var amtSign = tx.type === "claim" ? "-" : "+";
    return '<div class="fc-history-row" data-type="' + tx.type + '" style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;background:#fafafa;font-size:12px;">' +
      '<span style="width:8px;height:8px;border-radius:50%;background:' + dotColor + ';flex-shrink:0;"></span>' +
      '<span style="flex:1;color:#333;">' + escapeHtml(tx.description || tx.category) + "</span>" +
      '<span style="font-size:10px;color:#999;min-width:80px;text-align:right;">' + escapeHtml(tx.date) + "</span>" +
      '<span style="font-weight:600;min-width:70px;text-align:right;' + amtClass + '">' + amtSign + fmtPeso(tx.amount) + "</span>" +
      '<span style="font-size:10px;color:#999;min-width:60px;text-align:right;">' + escapeHtml(tx.status) + "</span>" +
      "</div>";
  }

  document.addEventListener("click", function (e) {
    var filterBtn = e.target.closest(".fc-history-filter");
    if (!filterBtn) return;
    var container = filterBtn.closest(".fc-history-filters");
    if (!container) return;
    container.querySelectorAll(".fc-history-filter").forEach(function (b) {
      b.style.background = "#fff";
      b.style.color = "";
      b.style.borderColor = "#ddd";
    });
    filterBtn.style.background = "#1a7a2e";
    filterBtn.style.color = "#fff";
    filterBtn.style.borderColor = "#1a7a2e";

    var filter = filterBtn.getAttribute("data-filter");
    var list = container.parentElement.querySelector(".fc-history-list");
    if (!list) return;
    list.querySelectorAll(".fc-history-row").forEach(function (row) {
      if (filter === "all" || row.getAttribute("data-type") === filter) {
        row.style.display = "flex";
      } else {
        row.style.display = "none";
      }
    });
  });
})();