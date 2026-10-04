// frontend/js/wizard.js — First-Run Setup Wizard & Model Onboarding
import { showToast } from './settings.js';

export function initWizard({ onWizardCompleted }) {
  const wizardModal = document.getElementById('wizardModal');
  const btnSkipWizard = document.getElementById('btnSkipWizard');
  const btnSkipWizardTop = document.getElementById('btnSkipWizardTop');
  const btnWizardDownloadBase = document.getElementById('btnWizardDownloadBase');
  const wizardProgressSection = document.getElementById('wizardProgressSection');
  const wizardStatusText = document.getElementById('wizardStatusText');
  const wizardPercentText = document.getElementById('wizardPercentText');
  const wizardProgressBar = document.getElementById('wizardProgressBar');
  const wizardSpeedText = document.getElementById('wizardSpeedText');
  const wizardEtaText = document.getElementById('wizardEtaText');

  let pollInterval = null;

  function openWizard() {
    if (!wizardModal) return;
    wizardModal.classList.add('open');
  }

  function closeWizard() {
    if (!wizardModal) return;
    wizardModal.classList.remove('open');
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  btnSkipWizard?.addEventListener('click', closeWizard);
  btnSkipWizardTop?.addEventListener('click', closeWizard);

  // Check if any model is installed on startup
  async function checkModelsOnStartup() {
    try {
      const res = await fetch('/api/models');
      if (!res.ok) return;
      const models = await res.json();
      const hasInstalled = models.some(m => m.installed);
      if (!hasInstalled) {
        // No models installed anywhere -> Open first-run onboarding wizard!
        openWizard();
      }
    } catch (err) {
      console.warn('Could not check models on startup:', err);
    }
  }

  // Trigger Base Model Download
  btnWizardDownloadBase?.addEventListener('click', async () => {
    btnWizardDownloadBase.disabled = true;
    btnWizardDownloadBase.classList.add('opacity-50', 'pointer-events-none');
    wizardProgressSection?.classList.remove('hidden');
    if (wizardStatusText) wizardStatusText.textContent = 'Đang khởi tạo kết nối tải mô hình Base...';

    try {
      const res = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: 'base' })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể bắt đầu tải mô hình');
      }

      startWizardProgressPolling();
    } catch (err) {
      if (wizardStatusText) wizardStatusText.textContent = `Lỗi: ${err.message}`;
      btnWizardDownloadBase.disabled = false;
      btnWizardDownloadBase.classList.remove('opacity-50', 'pointer-events-none');
      showToast(`Lỗi: ${err.message}`, 'error');
    }
  });

  function startWizardProgressPolling() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/models/progress');
        if (!res.ok) return;
        const data = await res.json();

        if (wizardPercentText) wizardPercentText.textContent = `${data.percent}%`;
        if (wizardProgressBar) wizardProgressBar.style.width = `${data.percent}%`;
        if (wizardSpeedText) wizardSpeedText.textContent = `${data.speed_mbps} MB/s (${data.downloaded_mb}/${data.total_mb} MB)`;
        if (wizardEtaText) {
          wizardEtaText.textContent = data.eta_seconds !== null ? `Còn ~${data.eta_seconds}s` : 'Đang tính...';
        }

        if (data.status === 'COMPLETED') {
          clearInterval(pollInterval);
          pollInterval = null;
          if (wizardStatusText) wizardStatusText.textContent = '✓ Tải mô hình Base thành công! Sẵn sàng sử dụng.';
          if (wizardProgressBar) wizardProgressBar.style.width = '100%';
          showToast('Đã tải mô hình Base thành công!', 'success');

          // Save default model as base
          try {
            await fetch('/api/settings', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ai: { whisper_model: 'base' } })
            });
          } catch (e) {}

          if (onWizardCompleted) onWizardCompleted();

          setTimeout(() => {
            closeWizard();
          }, 1200);

        } else if (data.status === 'FAILED') {
          clearInterval(pollInterval);
          pollInterval = null;
          if (wizardStatusText) wizardStatusText.textContent = `Tải thất bại: ${data.error}`;
          btnWizardDownloadBase.disabled = false;
          btnWizardDownloadBase.classList.remove('opacity-50', 'pointer-events-none');
          showToast(`Lỗi: ${data.error}`, 'error');
        }
      } catch (e) {
        console.warn('Wizard poll error:', e);
      }
    }, 500);
  }

  // Run initial check
  checkModelsOnStartup();

  return { openWizard, closeWizard, checkModelsOnStartup };
}
