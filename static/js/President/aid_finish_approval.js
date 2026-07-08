(function () {
  "use strict";

  const CSRF_HEADER_NAME = "X-CSRFToken";

  function getCSRFToken() {
    const el = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (el && el.value) return el.value;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function formatMoneyPHP(num) {
    const n = typeof num === "number" ? num : parseFloat(num || "0");
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency: "PHP",
    }).format(n);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  var FINISH_REQUESTS_URL = "/api/president/aid-post-finish-requests/";
  var APPROVE_URL = "/api/president/aid-post-finish-approve/";
  var REJECT_URL = "/api/president/aid-post-finish-reject/";

  async function getJSON(url) {
    const resp = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    const data = await resp.json().catch(function () {
      return {};
    });
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Request failed: " + url);
    }
    return data;
  }

  async function postForm(url, fd) {
    const csrf = getCSRFToken();
    var headers = {};
    if (csrf) {
      headers[CSRF_HEADER_NAME] = csrf;
    }
    var resp = await fetch(url, {
      method: "POST",
      body: fd,
      headers: headers,
      credentials: "same-origin",
    });
    var data = await resp.json().catch(function () {
      return {};
    });
    if (!resp.ok || !data.ok) {
      throw new Error((data && data.error) || "Server error.");
    }
    return data;
  }

  async function loadRequests() {
    try {
      var data = await getJSON(FINISH_REQUESTS_URL);
      renderRequests(data.posts || []);
      updateNotificationDot((data.posts || []).length);
    } catch (e) {
      showToast(e.message || "Failed to load finish requests.", true);
    }
  }

  function updateNotificationDot(count) {
    window.__finishApprovalCount = count;
    var dot = getEl("pres-finish-dot");
    if (dot) {
      if (count > 0) {
        dot.style.display = "inline-flex";
        dot.textContent = count > 99 ? "99+" : count;
      } else {
        dot.style.display = "none";
      }
    }
    if (typeof updatePresidentNotifDots === "function") {
      updatePresidentNotifDots();
    }
  }

  function renderRequests(posts) {
    var tbody = getEl("finishApprovalTableBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!posts || posts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#90a4ae;padding:30px;">No pending finish requests.</td></tr>';
      return;
    }

    posts.forEach(function (p) {
      var tr = document.createElement("tr");

      var rateColor = "#e53935";
      if (p.collection_rate >= 100) rateColor = "#1b5e20";
      else if (p.collection_rate >= 50) rateColor = "#fbc02d";

      var skipLabel = p.skip_remaining ? "Yes (auto-skip unpaid)" : "No";

      tr.innerHTML =
        "<td><strong>" + escapeHtml(p.member_name || "Unknown") + "</strong></td>" +
        "<td>" + escapeHtml(p.aid_label || "") + "</td>" +
        "<td>" + formatMoneyPHP(p.total_expected) + "</td>" +
        "<td>" + formatMoneyPHP(p.total_collected) + "</td>" +
        '<td style="font-weight:600;color:' + rateColor + ';">' + p.collection_rate + "%</td>" +
        "<td>" + escapeHtml(skipLabel) + "</td>" +
        "<td style='font-size:0.82rem;color:#90a4ae;'>" + escapeHtml(p.created_by || "") + "<br><small>" + escapeHtml(p.created_at || "") + "</small></td>" +
        '<td style="white-space:nowrap;">' +
        '<button class="btn-approve-finish" data-post-id="' + p.post_id + '" style="padding:6px 14px;border-radius:8px;border:1px solid #1b5e20;background:#1b5e20;color:#fff;font-weight:600;font-size:0.75rem;cursor:pointer;font-family:\'Poppins\',sans-serif;margin-right:4px;">Approve</button>' +
        '<button class="btn-reject-finish" data-post-id="' + p.post_id + '" style="padding:6px 14px;border-radius:8px;border:1px solid #c62828;background:#fff;color:#c62828;font-weight:600;font-size:0.75rem;cursor:pointer;font-family:\'Poppins\',sans-serif;">Reject</button>' +
        "</td>";

      tr.querySelector(".btn-approve-finish").addEventListener("click", function () {
        handleApprove(p.post_id, p.member_name);
      });
      tr.querySelector(".btn-reject-finish").addEventListener("click", function () {
        handleReject(p.post_id, p.member_name);
      });

      tbody.appendChild(tr);
    });
  }

  async function handleApprove(postId, memberName) {
    var result = await Swal.fire({
      title: "Approve Finish?",
      text: "This will mark " + (memberName || "this post") + " as finished and move it to history.",
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Yes, approve",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#1b5e20",
      reverseButtons: true,
    });
    if (!result.isConfirmed) return;

    try {
      var fd = new FormData();
      fd.append("post_id", postId);
      await postForm(APPROVE_URL, fd);
      showToast("Finish request approved. Post moved to history.", false);
      loadRequests();
    } catch (e) {
      showToast(e.message || "Failed to approve finish request.", true);
    }
  }

  async function handleReject(postId, memberName) {
    var result = await Swal.fire({
      title: "Reject Finish?",
      text: "The post will return to active state for " + (memberName || "this member") + ".",
      icon: "warning",
      input: "textarea",
      inputPlaceholder: "Reason for rejection (optional)...",
      showCancelButton: true,
      confirmButtonText: "Yes, reject",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#c62828",
      reverseButtons: true,
    });
    if (!result.isConfirmed) return;

    try {
      var fd = new FormData();
      fd.append("post_id", postId);
      var remarks = (result.value || "").trim();
      if (remarks) {
        fd.append("remarks", remarks);
      }
      await postForm(REJECT_URL, fd);
      showToast("Finish request rejected. Post returned to active state.", false);
      loadRequests();
    } catch (e) {
      showToast(e.message || "Failed to reject finish request.", true);
    }
  }

  window.AidFinishApproval = {
    loadRequests: loadRequests,
  };

  var _observer = null;

  document.addEventListener("turbo:load", function () {
    var tab = getEl("president-finish-approvals");
    if (tab) {
      if (tab.classList.contains("active")) {
        loadRequests();
      }
      _observer = new MutationObserver(function () {
        if (tab.classList.contains("active")) {
          loadRequests();
        }
      });
      _observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
    }
  });

  document.addEventListener("turbo:before-cache", function () {
    if (_observer) { _observer.disconnect(); _observer = null; }
  });
})();
