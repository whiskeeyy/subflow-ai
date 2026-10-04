// frontend/js/ui_dialog.js — Studio Dialog & Toast System
// Replaces primitive browser alert() with polished Dark-Theme Glassmorphism modals & floating toasts.

/**
 * Renders a non-blocking toast notification that slides in from top-right and auto-dismisses.
 * @param {string} message - Toast description
 * @param {'info'|'success'|'warning'|'error'} [type='info'] - Severity category
 * @param {number} [duration=3500] - Duration in milliseconds before fading out
 */
export function showToast(message, type = 'info', duration = 3500) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2.5 pointer-events-none max-w-sm w-full';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'pointer-events-auto transform translate-x-12 opacity-0 transition-all duration-300 ease-out bg-[#161b22]/95 backdrop-blur-md border border-[#30363d] shadow-2xl rounded-xl p-3.5 flex items-start gap-3 relative overflow-hidden';

  let iconSvg = '';
  let accentBorder = 'border-l-4 border-l-indigo-500';
  let progressBg = 'bg-indigo-500';

  if (type === 'success') {
    accentBorder = 'border-l-4 border-l-emerald-500';
    progressBg = 'bg-emerald-500';
    iconSvg = `<svg class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
  } else if (type === 'warning') {
    accentBorder = 'border-l-4 border-l-amber-500';
    progressBg = 'bg-amber-500';
    iconSvg = `<svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
  } else if (type === 'error') {
    accentBorder = 'border-l-4 border-l-rose-500';
    progressBg = 'bg-rose-500';
    iconSvg = `<svg class="w-4 h-4 text-rose-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
  } else {
    iconSvg = `<svg class="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
  }

  toast.classList.add(...accentBorder.split(' '));

  toast.innerHTML = `
    ${iconSvg}
    <div class="flex-1 min-w-0 pr-4">
      <p class="text-xs text-slate-200 font-medium leading-relaxed break-words">${message}</p>
    </div>
    <button type="button" class="btn-close-toast text-slate-500 hover:text-slate-300 p-0.5 rounded transition">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
    </button>
    <div class="toast-progress absolute bottom-0 left-0 h-0.5 ${progressBg} w-full transition-all linear" style="transition-duration: ${duration}ms;"></div>
  `;

  container.appendChild(toast);

  // Trigger smooth enter transition
  requestAnimationFrame(() => {
    toast.classList.remove('translate-x-12', 'opacity-0');
    toast.classList.add('translate-x-0', 'opacity-100');
    const pBar = toast.querySelector('.toast-progress');
    if (pBar) {
      setTimeout(() => { pBar.style.width = '0%'; }, 10);
    }
  });

  let dismissTimer = setTimeout(dismiss, duration);

  function dismiss() {
    clearTimeout(dismissTimer);
    toast.classList.remove('translate-x-0', 'opacity-100');
    toast.classList.add('translate-x-12', 'opacity-0');
    setTimeout(() => {
      if (toast.parentElement) toast.parentElement.removeChild(toast);
    }, 300);
  }

  toast.querySelector('.btn-close-toast')?.addEventListener('click', dismiss);
}

/**
 * Displays a high-fidelity Studio Error Modal with category, actionable advice, and technical traceback.
 * @param {Object} options
 * @param {string} options.title - Short informative title
 * @param {string} options.message - User-friendly error message
 * @param {string} [options.suggestion] - Actionable suggestion or advice
 * @param {string} [options.details] - Technical traceback or command log
 * @param {string} [options.actionText] - Label for primary button (e.g. "Mở Cài đặt")
 * @param {Function} [options.onAction] - Callback when primary button is clicked
 */
export function showErrorModal({ title, message, suggestion, details, actionText, onAction }) {
  let modal = document.getElementById('studioErrorModal');
  if (!modal) {
    console.error('studioErrorModal element not found in DOM');
    return;
  }

  const titleEl = document.getElementById('studioErrorTitle');
  const messageEl = document.getElementById('studioErrorMessage');
  const suggestionContainer = document.getElementById('studioErrorSuggestionContainer');
  const suggestionText = document.getElementById('studioErrorSuggestionText');
  const detailsContainer = document.getElementById('studioErrorDetailsContainer');
  const detailsText = document.getElementById('studioErrorDetailsText');
  const btnAction = document.getElementById('studioErrorBtnAction');
  const btnClose = document.getElementById('studioErrorBtnClose');
  const btnCopy = document.getElementById('studioErrorBtnCopy');

  if (titleEl) titleEl.textContent = title || 'Đã xảy ra sự cố';
  if (messageEl) messageEl.textContent = message || 'Không thể hoàn tất tác vụ.';

  if (suggestion && suggestionContainer && suggestionText) {
    suggestionText.textContent = suggestion;
    suggestionContainer.classList.remove('hidden');
  } else if (suggestionContainer) {
    suggestionContainer.classList.add('hidden');
  }

  if (details && detailsContainer && detailsText) {
    detailsText.textContent = details;
    detailsContainer.classList.remove('hidden');
  } else if (detailsContainer) {
    detailsContainer.classList.add('hidden');
  }

  if (actionText && onAction && btnAction) {
    btnAction.textContent = actionText;
    btnAction.classList.remove('hidden');
    btnAction.onclick = () => {
      closeErrorModal();
      onAction();
    };
  } else if (btnAction) {
    btnAction.classList.add('hidden');
    btnAction.onclick = null;
  }

  if (btnCopy) {
    btnCopy.onclick = () => {
      const fullLog = `[${title || 'Lỗi SubFlow AI'}]\n${message || ''}\n${suggestion ? 'Gợi ý: ' + suggestion + '\n' : ''}${details ? '\n--- Chi tiết kỹ thuật ---\n' + details : ''}`;
      navigator.clipboard.writeText(fullLog).then(() => {
        showToast('Đã sao chép mã lỗi vào bộ nhớ tạm!', 'success', 2000);
      }).catch(() => {
        showToast('Không thể sao chép tự động.', 'warning');
      });
    };
  }

  modal.classList.remove('hidden');

  function closeErrorModal() {
    modal.classList.add('hidden');
  }

  if (btnClose) btnClose.onclick = closeErrorModal;
  modal.onclick = (e) => {
    if (e.target === modal) closeErrorModal();
  };
}

/**
 * Displays an asynchronous confirmation modal.
 * @param {Object} options
 * @param {string} options.title - Confirmation title
 * @param {string} options.message - Confirmation description
 * @param {string} [options.confirmText='Đồng ý'] - Confirmation button label
 * @param {string} [options.cancelText='Hủy bỏ'] - Cancel button label
 * @param {boolean} [options.isDanger=false] - Whether primary action is destructive (rose color)
 * @returns {Promise<boolean>} Resolves true if confirmed, false if cancelled
 */
export function showConfirmModal({ title, message, confirmText = 'Đồng ý', cancelText = 'Hủy bỏ', isDanger = false }) {
  return new Promise((resolve) => {
    const modal = document.getElementById('studioConfirmModal');
    if (!modal) {
      resolve(window.confirm(`${title}\n\n${message}`));
      return;
    }

    const titleEl = document.getElementById('studioConfirmTitle');
    const msgEl = document.getElementById('studioConfirmMessage');
    const btnConfirm = document.getElementById('studioConfirmBtnYes');
    const btnCancel = document.getElementById('studioConfirmBtnNo');

    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;
    if (btnConfirm) {
      btnConfirm.textContent = confirmText;
      if (isDanger) {
        btnConfirm.className = 'px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 rounded-xl transition shadow-lg shadow-rose-900/20';
      } else {
        btnConfirm.className = 'px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition shadow-lg shadow-indigo-900/20';
      }
    }
    if (btnCancel) btnCancel.textContent = cancelText;

    modal.classList.remove('hidden');

    function cleanup(result) {
      modal.classList.add('hidden');
      if (btnConfirm) btnConfirm.onclick = null;
      if (btnCancel) btnCancel.onclick = null;
      modal.onclick = null;
      resolve(result);
    }

    if (btnConfirm) btnConfirm.onclick = () => cleanup(true);
    if (btnCancel) btnCancel.onclick = () => cleanup(false);
    modal.onclick = (e) => {
      if (e.target === modal) cleanup(false);
    };
  });
}
