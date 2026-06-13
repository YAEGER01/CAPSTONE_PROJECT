document.addEventListener("DOMContentLoaded", () => {
  const toggleButton = document.querySelector("[data-nav-toggle]");
  const navLinks = document.querySelector("[data-nav-links]");

  if (!toggleButton || !navLinks) {
    return;
  }

  toggleButton.addEventListener("click", () => {
    navLinks.classList.toggle("is-open");
  });
});

/**
 * Global password toggle function for all password fields in the system
 * Usage: <button onclick="togglePassword('fieldId', this)">
 */
function togglePassword(fieldId, buttonElement) {
  const field = document.getElementById(fieldId);
  if (!field) return;
  
  const icon = buttonElement.querySelector('i');
  const isPassword = field.type === 'password';
  
  field.type = isPassword ? 'text' : 'password';
  
  if (icon) {
    if (isPassword) {
      icon.classList.remove('fa-eye');
      icon.classList.add('fa-eye-slash');
    } else {
      icon.classList.remove('fa-eye-slash');
      icon.classList.add('fa-eye');
    }
  }
}
