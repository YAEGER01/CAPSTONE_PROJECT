(function () {
  const passwordInput = document.getElementById('password');
  const passwordToggle = document.getElementById('passwordToggle');
  const passwordToggleIcon = document.getElementById('passwordToggleIcon');
  const loginForm = document.getElementById('loginForm');

  if (!passwordInput || !passwordToggle || !passwordToggleIcon) {
    return;
  }

  passwordToggle.addEventListener('click', function () {
    const showingPassword = passwordInput.type === 'text';
    passwordInput.type = showingPassword ? 'password' : 'text';
    passwordToggle.setAttribute('aria-label', showingPassword ? 'Show password' : 'Hide password');
    passwordToggleIcon.className = showingPassword ? 'fa-regular fa-eye' : 'fa-regular fa-eye-slash';
  });

  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const formData = new FormData(loginForm);
      fetch(loginForm.action || window.location.href, {
        method: 'POST',
        headers: {
          'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.ok && data.redirect_url) {
          window.location.href = data.redirect_url;
        } else if (data && !data.ok) {
          const container = document.getElementById('loginError');
          if (container) {
            container.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> ' + (data.error || 'Login failed.');
            container.style.display = 'block';
          }
        }
      })
      .catch(function () {
        const container = document.getElementById('loginError');
        if (container) {
          container.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Network error. Please try again.';
          container.style.display = 'block';
        }
      });
    });
  }
})();
