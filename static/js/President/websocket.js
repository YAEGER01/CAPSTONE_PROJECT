(function () {
  "use strict";

  var WS_TOKEN = window.WS_AUTH_TOKEN || "";
  var WS_URL = (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws/president-dashboard/" + (WS_TOKEN ? "?token=" + encodeURIComponent(WS_TOKEN) : "");
  var ws = null;
  var wsReconnectTimer = null;

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
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
    if (msg.type === "ping" || msg.type === "pong" || msg.type === "connection_established") return;
    if (msg.type === "dashboard_refresh") {
      var section = msg.section || "all";
      if (typeof showToast === "function") {
        showToast("Updates available for " + section + ".", false);
      }
      refreshPresidentSection(section);
    }
    if (msg.type === "pending_queue_updated") {
      if (typeof showToast === "function") {
        showToast(msg.queue_type + " pending: " + msg.count + " item(s).", false);
      }
      refreshPresidentSection(msg.queue_type);
    }
    if (msg.type === "notification_summary") {
      if (msg.pending_count > 0 && typeof showToast === "function") {
        showToast(msg.message || "You have " + msg.pending_count + " pending item(s).", false);
      }
    }
  }

  function refreshPresidentSection(section) {
    if (section === "all" || section === "payments") {
      if (typeof loadPresidentialQueue === "function") {
        loadPresidentialQueue();
      }
    }
    if (section === "all" || section === "aids") {
      if (typeof loadPresidentialAidsQueue === "function") {
        loadPresidentialAidsQueue();
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    connectWebSocket();
  });
})();