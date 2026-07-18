(function () {
  "use strict";

  var WS_TOKEN = window.WS_AUTH_TOKEN || "";
  var WS_URL =
    (window.location.protocol === "https:" ? "wss://" : "ws://") +
    window.location.host +
    "/ws/auditor-dashboard/" +
    (WS_TOKEN ? "?token=" + encodeURIComponent(WS_TOKEN) : "");
  var ws = null;
  var wsReconnectTimer = null;

  function connectWebSocket() {
    if (
      ws &&
      (ws.readyState === WebSocket.OPEN ||
        ws.readyState === WebSocket.CONNECTING)
    )
      return;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      scheduleReconnect();
      return;
    }
    ws.onmessage = function (event) {
      try {
        var msg = JSON.parse(event.data);
        handleWsMessage(msg);
      } catch (e) {}
    };
    ws.onclose = function () {
      scheduleReconnect();
    };
    ws.onerror = function () {
      ws.close();
    };
  }

  function scheduleReconnect() {
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(connectWebSocket, 5000);
  }

  function handleWsMessage(msg) {
    if (
      msg.type === "ping" ||
      msg.type === "pong" ||
      msg.type === "connection_established"
    )
      return;

    if (
      msg.type === "dashboard_refresh" ||
      msg.type === "pending_queue_updated"
    ) {
      if (typeof refreshAll === "function") {
        refreshAll();
      }
      return;
    }

    if (msg.type === "notification_summary") {
      if (typeof refreshAll === "function") {
        refreshAll();
      }
      return;
    }

    if (
      msg.type === "aid_post_created" ||
      msg.type === "contribution_updated" ||
      msg.type === "aid_post_finished"
    ) {
      if (typeof refreshAll === "function") {
        refreshAll();
      }
      return;
    }

    if (msg.type === "release_notification") {
      showReleaseAckToast(msg);
      return;
    }
  }

  function showReleaseAckToast(msg) {
    var host = document.getElementById("toastContainer");
    if (!host) return;
    var toast = document.createElement("div");
    toast.className = "custom-toast";
    toast.style.cursor = "default";
    toast.innerHTML =
      '<div style="font-size:0.82rem;line-height:1.4;">' +
      "<strong>Release: " + escapeHtml(msg.member_name) + "'s " + escapeHtml(msg.aid_label) + "</strong><br>" +
      "&#x20B1;" + escapeHtml(String(msg.total_collected)) + " from " + msg.paid_count + "/" + msg.total_count + " members" +
      '<br><button class="ack-release-btn" data-post-id="' + msg.post_id + '" style="margin-top:6px;padding:4px 14px;border-radius:6px;border:1px solid #1b5e20;background:#e8f5e9;color:#1b5e20;font-size:0.75rem;font-weight:600;cursor:pointer;">Acknowledge</button>' +
      "</div>";
    host.appendChild(toast);
    setTimeout(function () { toast.classList.add("show"); }, 10);
    toast.querySelector(".ack-release-btn").addEventListener("click", function () {
      var btn = this;
      btn.disabled = true;
      btn.innerText = "...";
      fetch("/api/treasurer/aid-post-release-acknowledge/" + msg.post_id + "/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")?.value || "" },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          btn.innerText = data.ok ? "\u2713 Acknowledged" : "Failed";
          if (!data.ok) btn.disabled = false;
          setTimeout(function () { toast.remove(); }, 2000);
        })
        .catch(function () {
          btn.innerText = "Error";
          btn.disabled = false;
        });
    });
    setTimeout(function () {
      toast.classList.remove("show");
      setTimeout(function () { toast.remove(); }, 300);
    }, 15000);
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function stopReconnect() {
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
  }

  document.addEventListener("turbo:load", function () {
    connectWebSocket();
  });

  document.addEventListener("turbo:before-cache", function () {
    stopReconnect();
    if (ws) {
      // Prevent reconnect churn during page caching/transition.
      ws.onclose = null;
      ws.onerror = null;
      try {
        ws.close();
      } catch (e) {}
      ws = null;
    }
  });

  // If the page is being unloaded (tab close / hard refresh), avoid reconnect churn.
  window.addEventListener("beforeunload", function () {
    stopReconnect();
    if (ws) {
      ws.onclose = null;
      ws.onerror = null;
      try {
        ws.close();
      } catch (e) {}
      ws = null;
    }
  });
})();
