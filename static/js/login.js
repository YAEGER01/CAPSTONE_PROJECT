(function () {
  const passwordInput = document.getElementById('password');
  const passwordToggle = document.getElementById('passwordToggle');
  const passwordToggleIcon = document.getElementById('passwordToggleIcon');

  if (!passwordInput || !passwordToggle || !passwordToggleIcon) {
    return;
  }

  passwordToggle.addEventListener('click', function () {
    const showingPassword = passwordInput.type === 'text';
    passwordInput.type = showingPassword ? 'password' : 'text';
    passwordToggle.setAttribute('aria-label', showingPassword ? 'Show password' : 'Hide password');
    passwordToggleIcon.className = showingPassword ? 'fa-regular fa-eye' : 'fa-regular fa-eye-slash';
  });
})();
