(function () {
  "use strict";

  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    let response = await originalFetch(...args);

    if (response.status === 403 && response.headers.get("X-Zero-Trust-Challenge") === "true") {
      const verified = await triggerZeroTrustModal();
      if (verified) {
        return originalFetch(...args);
      }
    }
    return response;
  };

  function triggerZeroTrustModal() {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.style.position = "fixed";
      overlay.style.top = "0";
      overlay.style.left = "0";
      overlay.style.width = "100%";
      overlay.style.height = "100%";
      overlay.style.backgroundColor = "rgba(0, 0, 0, 0.6)";
      overlay.style.display = "flex";
      overlay.style.justifyContent = "center";
      overlay.style.alignItems = "center";
      overlay.style.zIndex = "99999";
      overlay.style.backdropFilter = "blur(5px)";

      const modal = document.createElement("div");
      modal.style.backgroundColor = "#fff";
      modal.style.padding = "30px";
      modal.style.borderRadius = "12px";
      modal.style.boxShadow = "0 8px 30px rgba(0,0,0,0.3)";
      modal.style.width = "400px";
      modal.style.textAlign = "center";
      modal.style.fontFamily = "system-ui, -apple-system, sans-serif";

      modal.innerHTML = `
        <div style="font-size: 40px; margin-bottom: 15px; color: #1b5e20;">🛡️</div>
        <h3 style="margin: 0 0 10px; color: #333;">Zero Trust Verification</h3>
        <p style="font-size: 14px; color: #666; margin-bottom: 20px;">
          For security, please enter the verification code sent to your registered email or push notification device.
        </p>
        <div id="zt-error" style="color: #c62828; font-size: 13px; margin-bottom: 15px; display: none;"></div>
        <input type="text" id="zt-otp" placeholder="000000" maxlength="6" style="width: 100%; padding: 12px; font-size: 18px; letter-spacing: 5px; text-align: center; border: 2px solid #ccc; border-radius: 6px; margin-bottom: 20px; box-sizing: border-box;" />
        <div style="display: flex; gap: 10px;">
          <button id="zt-verify-btn" style="flex: 1; padding: 12px; font-size: 15px; background: #1b5e20; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">Verify</button>
          <button id="zt-resend-btn" style="padding: 12px; font-size: 14px; background: #eceff1; color: #37474f; border: none; border-radius: 6px; cursor: pointer;">Resend</button>
        </div>
      `;

      overlay.appendChild(modal);
      document.body.appendChild(overlay);

      const otpInput = modal.querySelector("#zt-otp");
      const verifyBtn = modal.querySelector("#zt-verify-btn");
      const resendBtn = modal.querySelector("#zt-resend-btn");
      const errorDiv = modal.querySelector("#zt-error");

      sendChallenge();

      function sendChallenge() {
        errorDiv.style.display = "none";
        resendBtn.disabled = true;
        resendBtn.innerText = "Sending...";

        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

        originalFetch("/api/auth/zero-trust/challenge/", {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          }
        })
        .then(r => r.json())
        .then(data => {
          resendBtn.disabled = false;
          resendBtn.innerText = "Resend";
          if (!data.ok) {
            errorDiv.innerText = data.error || "Failed to send code.";
            errorDiv.style.display = "block";
          }
        })
        .catch(() => {
          resendBtn.disabled = false;
          resendBtn.innerText = "Resend";
          errorDiv.innerText = "Network error while sending code.";
          errorDiv.style.display = "block";
        });
      }

      resendBtn.addEventListener("click", sendChallenge);

      verifyBtn.addEventListener("click", () => {
        const otp = otpInput.value.trim();
        if (otp.length !== 6) {
          errorDiv.innerText = "Please enter a 6-digit code.";
          errorDiv.style.display = "block";
          return;
        }

        verifyBtn.disabled = true;
        verifyBtn.innerText = "Verifying...";
        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

        originalFetch("/api/auth/zero-trust/verify/", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrfToken,
          },
          body: new URLSearchParams({ otp: otp })
        })
        .then(r => r.json())
        .then(data => {
          verifyBtn.disabled = false;
          verifyBtn.innerText = "Verify";
          if (data.ok) {
            document.body.removeChild(overlay);
            resolve(true);
          } else {
            errorDiv.innerText = data.error || "Verification failed.";
            errorDiv.style.display = "block";
          }
        })
        .catch(() => {
          verifyBtn.disabled = false;
          verifyBtn.innerText = "Verify";
          errorDiv.innerText = "Network error. Please try again.";
          errorDiv.style.display = "block";
        });
      });
    });
  }
})();
