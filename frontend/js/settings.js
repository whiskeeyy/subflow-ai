// frontend/js/settings.js — Dynamic Settings Center & Hardware Diagnostics
import { hexToAssBgr } from './utils.js';
import { showConfirmModal } from './ui_dialog.js';

let currentSettings = null;
let currentDiagnostics = null;
let activeTab = 'storage';
let onUpdateCallback = null;

// Helper: Show floating toast notification
export function showToast(message, type = 'success') {
  let toastContainer = document.getElementById('settingsToastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'settingsToastContainer';
    toastContainer.className = 'fixed bottom-5 right-5 z-[250] flex flex-col space-y-2 pointer-events-none';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bg = type === 'success' ? 'bg-emerald-600' : type === 'error' ? 'bg-red-600' : 'bg-indigo-600';
  toast.className = `${bg} text-white text-xs font-medium px-4 py-2.5 rounded-xl shadow-2xl flex items-center space-x-2 transition-all duration-300 transform translate-y-4 opacity-0 pointer-events-auto`;
  
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span class="font-bold text-sm">${icon}</span><span>${message}</span>`;
  
  toastContainer.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-4', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('translate-y-4', 'opacity-0');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Convert ASS color (&H00BBGGRR&) to CSS hex (#RRGGBB)
function assBgrToHex(assStr) {
  if (!assStr) return '#ffff00';
  const clean = assStr.replace('&H', '').replace('&', '').replace('00', '');
  if (clean.length === 6) {
    const b = clean.substring(0, 2);
    const g = clean.substring(2, 4);
    const r = clean.substring(4, 6);
    return `#${r}${g}${b}`.toLowerCase();
  }
  return '#ffff00';
}

export async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) throw new Error('Không thể tải cấu hình từ máy chủ');
    const data = await res.json();
    currentSettings = data.settings;
    currentDiagnostics = data.diagnostics;

    updateHardwarePill(currentDiagnostics);
    populateSettingsForm(currentSettings, currentDiagnostics);
    return data;
  } catch (err) {
    console.error('Error loading settings:', err);
    showToast('Lỗi khi nạp cài đặt: ' + err.message, 'error');
  }
}

// Update top navbar hardware status indicator
function updateHardwarePill(diag) {
  const pill = document.getElementById('hwStatusPill');
  const dot = document.getElementById('hwStatusDot');
  const text = document.getElementById('hwStatusText');
  if (!pill || !diag) return;

  pill.classList.remove('hidden');
  if (diag.has_nvidia_gpu) {
    dot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
    const gpuShort = diag.gpu_name.replace('NVIDIA GeForce ', '').replace('NVIDIA ', '');
    const enc = diag.has_nvenc ? 'NVENC' : (diag.cuda_usable ? 'CUDA' : 'CPU');
    text.textContent = `🟢 ${gpuShort} (${enc})`;
    text.title = `GPU: ${diag.gpu_name} | VRAM: ${diag.vram_gb} GB | Encoder: ${diag.resolved_encoder} | AI: ${diag.resolved_device.toUpperCase()}`;
  } else {
    dot.className = 'w-2 h-2 rounded-full bg-amber-400';
    text.textContent = '🟡 CPU (int8)';
    text.title = 'Hệ thống đang chạy trên CPU (chưa phát hiện GPU NVIDIA tương thích)';
  }
}

// Populate values into modal inputs
function populateSettingsForm(settings, diag) {
  if (!settings) return;

  // 1. Storage
  const outDirInput = document.getElementById('settingOutputDir');
  if (outDirInput) outDirInput.value = settings.storage?.output_dir || '';

  const cleanAudioCb = document.getElementById('settingAutoCleanupAudio');
  if (cleanAudioCb) cleanAudioCb.checked = Boolean(settings.storage?.auto_cleanup_audio);

  const cleanSourceCb = document.getElementById('settingAutoCleanupSource');
  if (cleanSourceCb) cleanSourceCb.checked = Boolean(settings.storage?.auto_cleanup_source_video);

  // 2. AI Model & Language
  const modelInput = document.getElementById('settingWhisperModel');
  if (modelInput) modelInput.value = settings.ai?.whisper_model || 'base';

  const langSelect = document.getElementById('settingWhisperLang');
  if (langSelect) langSelect.value = settings.ai?.language || 'zh';

  // Load and render interactive model cards
  loadModelsList();

  // 3. Hardware & Acceleration
  const deviceSelect = document.getElementById('settingDevice');
  if (deviceSelect) {
    deviceSelect.value = settings.ai?.device || 'auto';
    const cudaOption = deviceSelect.querySelector('option[value="cuda"]');
    if (cudaOption && diag) {
      if (!diag.has_nvidia_gpu) {
        cudaOption.disabled = true;
        cudaOption.textContent = 'NVIDIA GPU (CUDA) — Không phát hiện card';
      } else if (!diag.cuda_usable) {
        cudaOption.textContent = 'NVIDIA GPU (CUDA) — Thiếu cuBLAS DLL (Tự động fallback CPU)';
      }
    }
  }

  const encSelect = document.getElementById('settingEncoder');
  if (encSelect) {
    encSelect.value = settings.hardware?.encoder || 'auto';
    const nvencOption = encSelect.querySelector('option[value="h264_nvenc"]');
    if (nvencOption && diag && !diag.has_nvenc) {
      nvencOption.disabled = true;
      nvencOption.textContent = 'h264_nvenc (GPU) — Chưa hỗ trợ';
    }
  }

  // GPU Card Info
  const gpuCard = document.getElementById('gpuInfoCard');
  if (gpuCard && diag) {
    if (diag.has_nvidia_gpu) {
      const badgeText = diag.cuda_usable ? 'CUDA & NVENC Khả dụng' : 'NVENC GPU + CPU int8 AI';
      const badgeClass = diag.cuda_usable ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300';
      gpuCard.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="text-xs font-semibold text-emerald-400 flex items-center space-x-1.5">
            <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>
            <span>${diag.gpu_name}</span>
          </span>
          <span class="text-[11px] font-mono px-2 py-0.5 rounded ${badgeClass}">${badgeText}</span>
        </div>
        <div class="grid grid-cols-3 gap-2 mt-2 text-[11px] text-slate-300">
          <div class="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span class="text-slate-500 block">Dung lượng VRAM:</span>
            <span class="font-mono font-semibold text-slate-200">${diag.vram_gb} GB</span>
          </div>
          <div class="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span class="text-slate-500 block">Bộ mã hóa NVENC:</span>
            <span class="font-semibold ${diag.has_nvenc ? 'text-emerald-400' : 'text-amber-400'}">${diag.has_nvenc ? 'Khả dụng' : 'Không'}</span>
          </div>
          <div class="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span class="text-slate-500 block">Tăng tốc Render:</span>
            <span class="font-semibold text-indigo-400">4x – 8x so với CPU</span>
          </div>
        </div>
      `;
    } else {
      gpuCard.innerHTML = `
        <div class="flex items-center space-x-2 text-xs text-amber-300">
          <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
          <span>Không tìm thấy GPU NVIDIA rời. Hệ thống đang sử dụng CPU int8 để xử lý an toàn.</span>
        </div>
      `;
    }
  }

  // 4. Translation
  const transEngine = document.getElementById('settingTransEngine');
  if (transEngine) transEngine.value = settings.translation?.engine || 'google_gtx';

  const transApiKey = document.getElementById('settingTransApiKey');
  if (transApiKey) transApiKey.value = settings.translation?.api_key || '';

  // 5. Subtitle Preset
  const preset = settings.subtitle_preset || {};
  const fontSizeSlider = document.getElementById('settingFontSize');
  const fontSizeVal = document.getElementById('settingFontSizeVal');
  if (fontSizeSlider) {
    fontSizeSlider.value = preset.font_size || 20;
    if (fontSizeVal) fontSizeVal.textContent = `${fontSizeSlider.value}px`;
  }

  const marginVSlider = document.getElementById('settingMarginV');
  const marginVVal = document.getElementById('settingMarginVVal');
  if (marginVSlider) {
    marginVSlider.value = preset.margin_v || 140;
    if (marginVVal) marginVVal.textContent = `${marginVSlider.value}px`;
  }

  const colorPicker = document.getElementById('settingColorPicker');
  const colorHex = document.getElementById('settingColorHex');
  const hexColor = assBgrToHex(preset.color_bgr);
  if (colorPicker) colorPicker.value = hexColor;
  if (colorHex) colorHex.value = hexColor.toUpperCase();

  const fontNameSelect = document.getElementById('settingFontName');
  if (fontNameSelect) fontNameSelect.value = preset.font_name || 'Arial Black';

  updateLivePreview();
}

function updateLivePreview() {
  const previewBox = document.getElementById('subPresetPreview');
  if (!previewBox) return;

  const fontName = document.getElementById('settingFontName')?.value || 'Arial Black';
  const fontSize = document.getElementById('settingFontSize')?.value || 20;
  const color = document.getElementById('settingColorPicker')?.value || '#ffff00';

  previewBox.style.fontFamily = `"${fontName}", sans-serif`;
  previewBox.style.fontSize = `${fontSize}px`;
  previewBox.style.color = color;
}

// --- Model Downloader & Manager Logic ---
let settingsPollInterval = null;

export async function loadModelsList() {
  const container = document.getElementById('modelsManagerContainer');
  try {
    const res = await fetch('/api/models');
    if (!res.ok) return [];
    const models = await res.json();
    renderModelsManager(models);
    return models;
  } catch (err) {
    if (container) container.innerHTML = `<div class="text-center py-4 text-xs text-red-400">Không thể nạp danh sách mô hình: ${err.message}</div>`;
    return [];
  }
}

export function renderModelsManager(models) {
  const container = document.getElementById('modelsManagerContainer');
  if (!container || !models) return;

  container.innerHTML = '';
  models.forEach(m => {
    const card = document.createElement('div');
    card.className = 'p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-slate-700/80 transition flex flex-col space-y-2.5';
    card.id = `modelCard_${m.id}`;

    const statusBadge = m.installed
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">✓ Đã có sẵn</span>`
      : `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">Chưa tải</span>`;

    const defaultBadge = m.is_default
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">⭐ Mặc định</span>`
      : '';

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="text-xs font-bold text-white">${m.name}</span>
          ${statusBadge}
          ${defaultBadge}
        </div>
        <div class="flex items-center space-x-2 text-[11px] font-mono text-slate-400">
          <span>${m.size_mb} MB</span>
          <span class="text-slate-600">&bull;</span>
          <span class="text-slate-400">${m.vram_req}</span>
        </div>
      </div>
      
      <p class="text-[11px] text-slate-400 leading-relaxed">${m.desc}</p>

      <!-- Action buttons & Progress row -->
      <div class="flex items-center justify-between pt-1">
        <div class="flex items-center space-x-2">
          ${!m.installed ? `
            <button type="button" class="btn-dl-model px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition flex items-center space-x-1" data-id="${m.id}">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
              <span>Tải về (${m.size_mb} MB)</span>
            </button>
          ` : `
            ${!m.is_default ? `
              <button type="button" class="btn-select-default-model px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-indigo-600 text-slate-300 hover:text-white text-xs transition border border-slate-700" data-id="${m.id}">
                Chọn làm mặc định
              </button>
            ` : ''}
            <button type="button" class="btn-del-model p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition border border-transparent hover:border-red-500/20 ${m.is_default ? 'opacity-30 pointer-events-none' : ''}" data-id="${m.id}" title="${m.is_default ? 'Không thể xóa mô hình mặc định' : 'Xóa mô hình khỏi ổ đĩa'}">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          `}
        </div>

        <!-- Inline Progress (hidden unless downloading this model) -->
        <div id="inlineProgress_${m.id}" class="hidden flex-1 ml-4 space-y-1">
          <div class="flex items-center justify-between text-[10px] text-slate-400 font-mono">
            <span class="inline-status">Đang tải...</span>
            <span class="inline-pct font-bold text-indigo-400">0%</span>
          </div>
          <div class="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800">
            <div class="inline-bar bg-gradient-to-r from-indigo-500 to-emerald-400 h-full w-0 transition-all duration-300 rounded-full"></div>
          </div>
        </div>
      </div>
    `;

    card.querySelector('.btn-dl-model')?.addEventListener('click', () => {
      triggerDownloadInSettings(m.id);
    });

    card.querySelector('.btn-select-default-model')?.addEventListener('click', async () => {
      await saveModelAsDefault(m.id);
    });

    card.querySelector('.btn-del-model')?.addEventListener('click', async () => {
      const confirmed = await showConfirmModal({
        title: 'Xóa mô hình AI',
        message: `Bạn có chắc muốn xóa mô hình '${m.name}' khỏi máy tính để giải phóng dung lượng không?`,
        confirmText: 'Xóa mô hình',
        cancelText: 'Giữ lại',
        isDanger: true
      });
      if (confirmed) {
        await deleteModelFromDisk(m.id);
      }
    });

    container.appendChild(card);
  });
}

async function saveModelAsDefault(modelId) {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai: { whisper_model: modelId } })
    });
    if (!res.ok) throw new Error('Không thể lưu cài đặt');
    showToast(`Đã chọn mô hình '${modelId}' làm mặc định!`, 'success');
    const input = document.getElementById('settingWhisperModel');
    if (input) input.value = modelId;
    await loadSettings();
    await loadModelsList();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteModelFromDisk(modelId) {
  try {
    const res = await fetch(`/api/models/${modelId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể xóa mô hình');
    }
    showToast(`Đã xóa mô hình '${modelId}' thành công.`, 'info');
    await loadModelsList();
    await loadSettings();
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, 'error');
  }
}

function triggerDownloadInSettings(modelId) {
  fetch('/api/models/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id: modelId })
  })
  .then(async res => {
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể bắt đầu tải');
    }
    return res.json();
  })
  .then(data => {
    showToast(`Bắt đầu tải mô hình '${modelId}'...`, 'info');
    const inlineEl = document.getElementById(`inlineProgress_${modelId}`);
    if (inlineEl) inlineEl.classList.remove('hidden');

    if (settingsPollInterval) clearInterval(settingsPollInterval);
    settingsPollInterval = setInterval(async () => {
      try {
        const pRes = await fetch('/api/models/progress');
        if (!pRes.ok) return;
        const pData = await pRes.json();
        
        const cardProgress = document.getElementById(`inlineProgress_${pData.model_id}`);
        if (cardProgress) {
          cardProgress.classList.remove('hidden');
          const statusSpan = cardProgress.querySelector('.inline-status');
          const pctSpan = cardProgress.querySelector('.inline-pct');
          const barSpan = cardProgress.querySelector('.inline-bar');

          if (statusSpan) statusSpan.textContent = `Đang tải: ${pData.speed_mbps} MB/s (${pData.downloaded_mb}/${pData.total_mb} MB)`;
          if (pctSpan) pctSpan.textContent = `${pData.percent}%`;
          if (barSpan) barSpan.style.width = `${pData.percent}%`;
        }

        if (pData.status === 'COMPLETED') {
          clearInterval(settingsPollInterval);
          settingsPollInterval = null;
          showToast(`Tải thành công mô hình '${pData.model_id}'!`, 'success');
          await loadModelsList();
          await loadSettings();
        } else if (pData.status === 'FAILED') {
          clearInterval(settingsPollInterval);
          settingsPollInterval = null;
          showToast(`Lỗi tải mô hình: ${pData.error}`, 'error');
          await loadModelsList();
        }
      } catch (err) {
        console.warn('Settings poll error:', err);
      }
    }, 500);
  })
  .catch(err => {
    showToast(`Lỗi: ${err.message}`, 'error');
  });
}

export function openSettingsModal(defaultTab = 'storage') {
  const modal = document.getElementById('settingsModal');
  if (!modal) return;

  switchTab(defaultTab);
  modal.classList.add('open');
  modal.classList.remove('pointer-events-none', 'opacity-0');
}

export function closeSettingsModal() {
  const modal = document.getElementById('settingsModal');
  if (!modal) return;
  modal.classList.remove('open');
  modal.classList.add('pointer-events-none', 'opacity-0');
}

function switchTab(tabId) {
  activeTab = tabId;
  if (tabId === 'ai') {
    loadModelsList();
  }
  const tabButtons = document.querySelectorAll('.settings-tab-btn');
  const tabPanels = document.querySelectorAll('.settings-tab-panel');

  tabButtons.forEach(btn => {
    if (btn.dataset.tab === tabId) {
      btn.className = 'settings-tab-btn w-full flex items-center space-x-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 transition text-left';
    } else {
      btn.className = 'settings-tab-btn w-full flex items-center space-x-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent transition text-left';
    }
  });

  tabPanels.forEach(panel => {
    if (panel.dataset.panel === tabId) {
      panel.classList.remove('hidden');
    } else {
      panel.classList.add('hidden');
    }
  });
}

async function handleBrowseFolder() {
  const btn = document.getElementById('btnBrowseOutputDir');
  const originalText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg class="w-3.5 h-3.5 animate-spin inline mr-1" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Đang mở...`;
  }

  try {
    const res = await fetch('/api/settings/browse-folder', { method: 'POST' });
    const data = await res.json();
    if (data.path) {
      const outDirInput = document.getElementById('settingOutputDir');
      if (outDirInput) outDirInput.value = data.path;
      showToast(`Đã chọn: ${data.path}`);
    }
  } catch (err) {
    showToast('Lỗi mở hộp thoại chọn thư mục: ' + err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
}

async function handleSaveSettings() {
  const btn = document.getElementById('btnSaveSettings');
  if (btn) btn.disabled = true;

  // Gather values
  const colorHex = document.getElementById('settingColorPicker')?.value || '#ffff00';
  const payload = {
    storage: {
      output_dir: document.getElementById('settingOutputDir')?.value.trim() || '',
      auto_cleanup_audio: Boolean(document.getElementById('settingAutoCleanupAudio')?.checked),
      auto_cleanup_source_video: Boolean(document.getElementById('settingAutoCleanupSource')?.checked)
    },
    ai: {
      whisper_model: document.getElementById('settingWhisperModel')?.value || 'base',
      device: document.getElementById('settingDevice')?.value || 'auto',
      language: document.getElementById('settingWhisperLang')?.value || 'zh'
    },
    hardware: {
      encoder: document.getElementById('settingEncoder')?.value || 'auto',
      gpu_device_id: 0
    },
    translation: {
      engine: document.getElementById('settingTransEngine')?.value || 'google_gtx',
      api_key: document.getElementById('settingTransApiKey')?.value.trim() || ''
    },
    subtitle_preset: {
      color_bgr: hexToAssBgr(colorHex),
      font_size: parseInt(document.getElementById('settingFontSize')?.value, 10) || 20,
      margin_v: parseInt(document.getElementById('settingMarginV')?.value, 10) || 140,
      font_name: document.getElementById('settingFontName')?.value || 'Arial Black'
    }
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || 'Lưu cài đặt thất bại');

    currentSettings = result.settings;
    showToast('Đã lưu cấu hình hệ thống thành công!', 'success');
    closeSettingsModal();

    if (onUpdateCallback) {
      onUpdateCallback(currentSettings);
    }
    // Refresh hardware indicator
    loadSettings();
  } catch (err) {
    showToast('Lỗi khi lưu cài đặt: ' + err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleResetSettings() {
  const confirmed = await showConfirmModal({
    title: 'Khôi phục cài đặt gốc',
    message: 'Bạn có chắc chắn muốn khôi phục toàn bộ cài đặt về mặc định của nhà sản xuất? Các cấu hình hiện tại sẽ được làm mới.',
    confirmText: 'Khôi phục mặc định',
    cancelText: 'Hủy bỏ',
    isDanger: true
  });
  if (!confirmed) {
    return;
  }

  try {
    const res = await fetch('/api/settings/reset', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Không thể khôi phục');

    currentSettings = data.settings;
    populateSettingsForm(currentSettings, currentDiagnostics);
    showToast('Đã khôi phục cài đặt gốc thành công!', 'success');

    if (onUpdateCallback) {
      onUpdateCallback(currentSettings);
    }
  } catch (err) {
    showToast('Lỗi khôi phục: ' + err.message, 'error');
  }
}

export function initSettings({ onSettingsUpdated } = {}) {
  onUpdateCallback = onSettingsUpdated;

  // Tab switching listeners
  document.querySelectorAll('.settings-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Modal open & close
  document.getElementById('btnNavSettings')?.addEventListener('click', () => openSettingsModal());
  document.getElementById('btnCloseSettingsModal')?.addEventListener('click', closeSettingsModal);
  document.getElementById('btnCancelSettings')?.addEventListener('click', closeSettingsModal);

  // Backdrop click closes
  const modal = document.getElementById('settingsModal');
  modal?.addEventListener('click', (e) => {
    if (e.target === modal) closeSettingsModal();
  });

  // Esc key listener
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.classList.contains('open')) {
      closeSettingsModal();
    }
  });

  // Actions
  document.getElementById('btnBrowseOutputDir')?.addEventListener('click', handleBrowseFolder);
  document.getElementById('btnSaveSettings')?.addEventListener('click', handleSaveSettings);
  document.getElementById('btnResetSettings')?.addEventListener('click', handleResetSettings);

  // Open output dir in Windows Explorer
  document.getElementById('btnOpenOutputDir')?.addEventListener('click', async () => {
    const p = document.getElementById('settingOutputDir')?.value;
    if (p) {
      try {
        await fetch(`/api/open-folder?path=${encodeURIComponent(p)}`);
      } catch (err) {
        showToast('Lỗi mở thư mục: ' + err.message, 'error');
      }
    }
  });

  // Subtitle preset live preview listeners
  const fontSizeSlider = document.getElementById('settingFontSize');
  fontSizeSlider?.addEventListener('input', (e) => {
    const val = document.getElementById('settingFontSizeVal');
    if (val) val.textContent = `${e.target.value}px`;
    updateLivePreview();
  });

  const marginVSlider = document.getElementById('settingMarginV');
  marginVSlider?.addEventListener('input', (e) => {
    const val = document.getElementById('settingMarginVVal');
    if (val) val.textContent = `${e.target.value}px`;
    updateLivePreview();
  });

  const colorPicker = document.getElementById('settingColorPicker');
  const colorHex = document.getElementById('settingColorHex');
  colorPicker?.addEventListener('input', (e) => {
    if (colorHex) colorHex.value = e.target.value.toUpperCase();
    updateLivePreview();
  });
  colorHex?.addEventListener('input', (e) => {
    if (colorPicker && /^#[0-9A-F]{6}$/i.test(e.target.value)) {
      colorPicker.value = e.target.value;
      updateLivePreview();
    }
  });

  document.getElementById('settingFontName')?.addEventListener('change', updateLivePreview);

  // Initial load
  loadSettings();

  return {
    openSettingsModal,
    closeSettingsModal,
    loadSettings,
    loadModelsList,
    getSettings: () => currentSettings,
    getDiagnostics: () => currentDiagnostics
  };
}
