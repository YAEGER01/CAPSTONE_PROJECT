/**
 * SweetAlert2 Helper Functions
 * Provides reusable SWAL notifications throughout the system
 */

// Show loading/processing dialog
function showLoading(title = 'Processing...', message = 'Please wait...') {
  Swal.fire({
    title: title,
    html: message,
    icon: 'info',
    allowOutsideClick: false,
    allowEscapeKey: false,
    didOpen: (modal) => {
      Swal.showLoading();
    }
  });
}

// Show success message
function showSuccess(title = 'Success!', message = 'Operation completed successfully.', timer = 2000) {
  return Swal.fire({
    title: title,
    text: message,
    icon: 'success',
    timer: timer,
    timerProgressBar: true,
    showConfirmButton: false,
    allowOutsideClick: false
  });
}

// Show error message
function showError(title = 'Error!', message = 'Something went wrong. Please try again.') {
  return Swal.fire({
    title: title,
    text: message,
    icon: 'error',
    confirmButtonColor: '#dc2626'
  });
}

// Show confirmation dialog
function showConfirm(title = 'Are you sure?', message = 'This action cannot be undone.', confirmText = 'Yes, confirm', cancelText = 'Cancel') {
  return Swal.fire({
    title: title,
    text: message,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#3d4ae7',
    cancelButtonColor: '#6b7280',
    confirmButtonText: confirmText,
    cancelButtonText: cancelText,
    allowOutsideClick: false
  });
}

// Show info message
function showInfo(title = 'Information', message = 'Please note this information.') {
  return Swal.fire({
    title: title,
    text: message,
    icon: 'info',
    confirmButtonColor: '#3d4ae7'
  });
}

// Form submission with loading indicator
function submitFormWithLoader(form, successMessage = 'Saved successfully!') {
  showLoading('Processing...', '<i class="fa-solid fa-spinner fa-spin"></i> Please wait while we process your request...');
  
  // Simulate form submission
  setTimeout(() => {
    form.submit();
  }, 500);
}

// Handle form submission with AJAX-style feedback
function handleFormSubmit(event, form, actionName = 'Operation') {
  event.preventDefault();
  
  showLoading(`${actionName}...`, '<i class="fa-solid fa-spinner fa-spin"></i> Processing your request...');
  
  // Get form data
  const formData = new FormData(form);
  
  // Disable submit button
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) submitBtn.disabled = true;
  
  setTimeout(() => {
    form.submit();
  }, 800);
}

// Show warning with auto-dismiss
function showWarning(title = 'Warning', message = 'Please be careful.', timer = 4000) {
  return Swal.fire({
    title: title,
    text: message,
    icon: 'warning',
    timer: timer,
    timerProgressBar: true,
    showConfirmButton: false
  });
}

// Confirm action with specific message
function confirmAction(actionName = 'delete', itemName = '') {
  const message = itemName 
    ? `Are you sure you want to ${actionName} "${itemName}"? This action cannot be undone.`
    : `Are you sure you want to ${actionName}? This action cannot be undone.`;
  
  return showConfirm(`${actionName.charAt(0).toUpperCase() + actionName.slice(1)}?`, message);
}

// Show progress notification
function showProgress(message = 'Loading...', percent = 0) {
  Swal.fire({
    title: 'Processing',
    html: `
      <div style="margin: 20px 0;">
        <p>${message}</p>
        <div style="width: 100%; height: 6px; background-color: #e5e7eb; border-radius: 3px; overflow: hidden;">
          <div style="width: ${percent}%; height: 100%; background-color: #3d4ae7; transition: width 0.3s ease;"></div>
        </div>
        <p style="margin-top: 10px; font-size: 0.9rem; color: #6b7280;">${percent}%</p>
      </div>
    `,
    icon: 'info',
    allowOutsideClick: false,
    allowEscapeKey: false,
    showConfirmButton: false,
    didOpen: (modal) => {
      // Make progress element available for updates
      window.currentSwalModal = modal;
    }
  });
}

// Update progress (requires showProgress to be called first)
function updateProgress(message, percent) {
  if (window.currentSwalModal) {
    Swal.update({
      html: `
        <div style="margin: 20px 0;">
          <p>${message}</p>
          <div style="width: 100%; height: 6px; background-color: #e5e7eb; border-radius: 3px; overflow: hidden;">
            <div style="width: ${percent}%; height: 100%; background-color: #3d4ae7; transition: width 0.3s ease;"></div>
          </div>
          <p style="margin-top: 10px; font-size: 0.9rem; color: #6b7280;">${percent}%</p>
        </div>
      `
    });
  }
}

// Close current SWAL
function closeSwal() {
  Swal.close();
}

// Toast notification (top-right corner)
const Toast = Swal.mixin({
  toast: true,
  position: 'top-end',
  showConfirmButton: false,
  timer: 3000,
  timerProgressBar: true,
  didOpen: (toast) => {
    toast.addEventListener('mouseenter', Swal.stopTimer);
    toast.addEventListener('mouseleave', Swal.resumeTimer);
  }
});

function showToast(icon = 'success', title = 'Done!') {
  return Toast.fire({
    icon: icon,
    title: title
  });
}

// Combine confirmation with action
function confirmAndSubmit(form, actionName = 'Save changes', itemName = '') {
  confirmAction(actionName, itemName).then((result) => {
    if (result.isConfirmed) {
      handleFormSubmit(
        { preventDefault: () => {} },
        form,
        actionName
      );
    }
  });
}
