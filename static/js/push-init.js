(function () {
  "use strict";

  var VAPID_PUBLIC_KEY = window.VAPID_PUBLIC_KEY || null;
  if (!VAPID_PUBLIC_KEY) return;

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var rawData = atob(base64);
    var output = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      output[i] = rawData.charCodeAt(i);
    }
    return output;
  }

  function getCsrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function subscribeUser(registration) {
    registration.pushManager
      .subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      })
      .then(function (subscription) {
        var subJson = subscription.toJSON();
        fetch("/api/push/subscribe/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            endpoint: subJson.endpoint,
            keys: subJson.keys,
          }),
        }).catch(function () {});
      })
      .catch(function () {});
  }

  if ("serviceWorker" in navigator && "PushManager" in window) {
    navigator.serviceWorker
      .register("/static/js/service-worker.js")
      .then(function (registration) {
        if (Notification.permission === "granted") {
          subscribeUser(registration);
        } else if (Notification.permission === "default") {
          Notification.requestPermission().then(function (permission) {
            if (permission === "granted") {
              subscribeUser(registration);
            }
          });
        }
      })
      .catch(function () {});
  }
})();
