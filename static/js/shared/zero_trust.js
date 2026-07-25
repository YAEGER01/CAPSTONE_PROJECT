(function () {
  "use strict";

  var originalFetch = window.fetch;
  window.fetch = async function () {
    var args = arguments;
    var response = await originalFetch.apply(window, args);

    if (response.redirected && response.url && response.url.indexOf("session_expired=1") !== -1) {
      window.location.href = response.url;
      return new Response("", { status: 0, statusText: "Session expired" });
    }

    if (response.status === 403 && response.headers.get("X-Zero-Trust-Challenge") === "true") {
      var verified = await triggerZeroTrustModal();
      if (verified) {
        return originalFetch.apply(window, args);
      }
    }
    return response;
  };

  function getCsrf() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  var ztModalId = "zt-modal-overlay";

  function removeModal() {
    var existing = document.getElementById(ztModalId);
    if (existing) existing.remove();
    document.body.style.overflow = "";
  }

  function triggerZeroTrustModal(action) {
    action = action || "";
    return new Promise(function (resolve) {
      removeModal();

      var overlay = document.createElement("div");
      overlay.id = ztModalId;
      overlay.style.cssText =
        "position:fixed;top:0;left:0;width:100vw;height:100vh;" +
        "background:rgba(0,0,0,0.4);z-index:9999;display:flex;" +
        "align-items:center;justify-content:center;";

      var card = document.createElement("div");
      card.style.cssText =
        "background:white;border-radius:14px;width:90%;max-width:420px;" +
        "padding:28px;box-shadow:0 15px 40px rgba(0,0,0,0.15);" +
        "text-align:center;position:relative;";

      card.innerHTML =
        '<div style="font-size:36px;margin-bottom:6px;color:#1b5e20;">&#128522;</div>' +
        '<h3 style="color:#1b5e20;margin-bottom:6px;font-size:1.2rem;">Quick Security Check</h3>' +
        '<p style="font-size:13px;color:#666;margin-bottom:16px;line-height:1.5;">' +
        "We've sent a one-time code to your registered email. " +
        "Enter it below to continue" +
        (action ? ' with <strong>' + action + "</strong>." : ".") +
        "</p>" +
        '<div id="zt-error" style="color:#c62828;font-size:13px;margin-bottom:12px;display:none;"></div>' +
        '<input type="text" id="zt-otp" maxlength="6" placeholder="000000"' +
        ' style="width:80%;padding:12px;font-size:20px;text-align:center;letter-spacing:5px;' +
        'border:2px solid #ddd;border-radius:8px;margin:0 auto 16px;display:block;outline:none;" />' +
        '<div style="display:flex;gap:10px;justify-content:center;margin-bottom:12px;">' +
        '<button id="zt-resend-btn" type="button"' +
        ' style="padding:8px 20px;background:#eceff1;color:#37474f;border:none;border-radius:6px;' +
        'cursor:pointer;font-size:13px;font-weight:600;">Resend Code</button>' +
        "</div>" +
        '<div style="display:flex;gap:10px;justify-content:center;">' +
        '<button id="zt-cancel-btn" type="button"' +
        ' style="padding:10px 24px;background:#546e7a;color:#fff;border:none;border-radius:8px;' +
        'cursor:pointer;font-size:14px;font-weight:600;">Cancel</button>' +
        '<button id="zt-verify-btn" type="button"' +
        ' style="padding:10px 24px;background:#1b5e20;color:#fff;border:none;border-radius:8px;' +
        'cursor:pointer;font-size:14px;font-weight:600;">Verify</button>' +
        "</div>";

      overlay.appendChild(card);
      document.body.appendChild(overlay);
      document.body.style.overflow = "hidden";

      var otpInput = document.getElementById("zt-otp");
      var errorDiv = document.getElementById("zt-error");
      var resendBtn = document.getElementById("zt-resend-btn");
      var verifyBtn = document.getElementById("zt-verify-btn");
      var cancelBtn = document.getElementById("zt-cancel-btn");

      function sendChallenge() {
        errorDiv.style.display = "none";
        resendBtn.disabled = true;
        resendBtn.textContent = "Sending...";
        var body = new URLSearchParams();
        if (action) body.append("action", action);

        originalFetch("/api/auth/zero-trust/challenge/", {
          method: "POST",
          headers: { "X-CSRFToken": getCsrf() },
          body: body,
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            resendBtn.disabled = false;
            resendBtn.textContent = "Resend Code";
            if (!data.ok) {
              errorDiv.textContent = data.error || "Failed to send code.";
              errorDiv.style.display = "block";
            }
          })
          .catch(function () {
            resendBtn.disabled = false;
            resendBtn.textContent = "Resend Code";
            errorDiv.textContent = "Network error while sending code.";
            errorDiv.style.display = "block";
          });
      }

      function verifyOtp() {
        var otp = otpInput.value.trim();
        if (otp.length !== 6) {
          errorDiv.textContent = "Please enter a 6-digit code.";
          errorDiv.style.display = "block";
          return;
        }
        verifyBtn.disabled = true;
        verifyBtn.textContent = "Verifying...";
        errorDiv.style.display = "none";

        originalFetch("/api/auth/zero-trust/verify/", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCsrf(),
          },
          body: new URLSearchParams({ otp: otp }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            verifyBtn.disabled = false;
            verifyBtn.textContent = "Verify";
            if (data.ok) {
              removeModal();
              resolve(true);
            } else {
              errorDiv.textContent = data.error || "Verification failed.";
              errorDiv.style.display = "block";
            }
          })
          .catch(function () {
            verifyBtn.disabled = false;
            verifyBtn.textContent = "Verify";
            errorDiv.textContent = "Network error. Please try again.";
            errorDiv.style.display = "block";
          });
      }

      function handleCancel() {
        removeModal();
        resolve(false);
      }

      sendChallenge();

      otpInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") verifyOtp();
      });

      resendBtn.addEventListener("click", sendChallenge);
      verifyBtn.addEventListener("click", verifyOtp);
      cancelBtn.addEventListener("click", handleCancel);
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) handleCancel();
      });

      otpInput.focus();
    });
  }

  window.ensureZeroTrust = async function (action) {
    try {
      var resp = await originalFetch("/api/auth/zero-trust/status/", {
        method: "GET",
        headers: { "X-CSRFToken": getCsrf() },
      });
      var data = await resp.json();
      if (data.ok && data.verified) return true;
    } catch (e) {
      console.error("Zero-trust status check failed:", e);
      var toast = document.getElementById("toastContainer");
      if (toast) {
        var t = document.createElement("div");
        t.className = "custom-toast toast-error";
        t.innerHTML = '<p style="font-size:0.85rem;font-weight:500;margin:0;">Security check failed. Please try again.</p>';
        toast.appendChild(t);
        setTimeout(function () { t.classList.add("show"); }, 10);
        setTimeout(function () {
          t.classList.remove("show");
          setTimeout(function () { t.remove(); }, 300);
        }, 4000);
      }
    }
    return await triggerZeroTrustModal(action);
  };
})();
