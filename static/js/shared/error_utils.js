function navigateToError(code, title, message, details) {
  const params = new URLSearchParams();
  if (code) params.set("code", code);
  if (title) params.set("title", title);
  if (message) params.set("message", message);
  if (details) params.set("details", details);
  if (window.Turbo && Turbo.visit) {
    Turbo.visit("/error/?" + params.toString());
  } else {
    window.location.href = "/error/?" + params.toString();
  }
}

function handleApiError(resp, data) {
  const status = resp ? resp.status : 0;
  if (status === 403) {
    navigateToError("403", "Access Denied", data && data.error ? data.error : "Forbidden for this role.", "This security anomaly event has been recorded in the central system audit log.");
    return true;
  }
  if (status === 401) {
    navigateToError("401", "Unauthorized", data && data.error ? data.error : "Authentication required.", "Please log in again to continue.");
    return true;
  }
  if (status >= 500) {
    navigateToError("500", "Server Error", data && data.error ? data.error : "An internal server error occurred.", "Please try again later or contact support.");
    return true;
  }
  return false;
}