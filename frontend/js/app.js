import { parseSRT, serializeCuesToSRT, hexToAssBgr, downloadBlob } from './utils.js';
import { initPlayer } from './player.js';
import { initEditor } from './editor.js';
import { initPipeline } from './pipeline.js';
import { initHistoryDrawer } from './history.js';
import { initBatchQueue } from './batch.js';
import { initSettings, openSettingsModal } from './settings.js';

// --- State ---
let cues = [];
let originalAiSrt = '';
let currentTaskId = '';
let currentTaskTitle = '';
let lastActiveCueId = null;
let selectedFile = null;
let lastOutputDir = '';
let currentWorkspaceTab = 'single';

// --- DOM Elements ---
const $ = id => document.getElementById(id);
const dropzone = $('dropzone');
const videoFileInput = $('videoFileInput');
const fileSelectedBadge = $('fileSelectedBadge');
const selectedFileName = $('selectedFileName');
const selectedFileSize = $('selectedFileSize');
const btnStart = $('btnStart');
const btnStartText = $('btnStartText');
const btnSpinner = $('btnSpinner');
const progressSection = $('progressSection');
const progressBar = $('progressBar');
const progressPercent = $('progressPercent');
const progressStepLabel = $('progressStepLabel');
const srtEditorSection = $('srtEditorSection');
const previewVideoWrapper = $('previewVideoWrapper');
const previewPlayer = $('previewPlayer');
const subOverlay = $('subOverlay');
const videoRatioBadge = $('videoRatioBadge');
const previewResText = $('previewResText');
const cueCardsContainer = $('cueCardsContainer');
const srtTextarea = $('srtTextarea');
const cueCountBadge = $('cueCountBadge');
const btnToggleEditorMode = $('btnToggleEditorMode');
const toggleModeIcon = $('toggleModeIcon');
const toggleModeText = $('toggleModeText');
const btnExportSrt = $('btnExportSrt');
const btnExportVtt = $('btnExportVtt');
const btnResetSrt = $('btnResetSrt');
const btnConfirmSrt = $('btnConfirmSrt');
const subColorPicker = $('subColorPicker');
const subColorVal = $('subColorVal');
const subFontSizeSlider = $('subFontSizeSlider');
const subFontSizeVal = $('subFontSizeVal');
const subMarginVSlider = $('subMarginVSlider');
const subMarginVVal = $('subMarginVVal');
const resultCard = $('resultCard');
const finalVideoPlayer = $('finalVideoPlayer');
const btnDownloadFinalVideo = $('btnDownloadFinalVideo');
const btnBackToEditor = $('btnBackToEditor');
const outputDirPath = $('outputDirPath');
const btnOpenFolder = $('btnOpenFolder');
const terminalLogs = $('terminalLogs');
const btnClearLog = $('btnClearLog');
const connectionStatus = $('connectionStatus');

// --- Navbar & Workspace DOM Elements ---
const tabBtnSingle = $('tabBtnSingle');
const tabBtnBatch = $('tabBtnBatch');
const singleWorkflowSection = $('singleWorkflowSection');
const batchWorkflowSection = $('batchWorkflowSection');
const batchDropzone = $('batchDropzone');
const batchFileInput = $('batchFileInput');
const btnNavOpenFolder = $('btnNavOpenFolder');
const btnNavSettings = $('btnNavSettings');
const hwStatusPill = $('hwStatusPill');

// --- Helpers ---
function appendLog(message, type = 'info') {
  const time = new Date().toLocaleTimeString('vi-VN');
  const div = document.createElement('div');
  let colorClass = 'text-slate-300', tag = '[INFO]';
  if (type === 'success') { colorClass = 'text-emerald-400 font-semibold'; tag = '[OK]'; }
  if (type === 'warn') { colorClass = 'text-amber-400 font-semibold'; tag = '[ACTION]'; }
  if (type === 'error') { colorClass = 'text-red-400 font-semibold'; tag = '[ERROR]'; }
  if (type === 'system') { colorClass = 'text-indigo-400'; tag = '[TASK]'; }
  div.className = `${colorClass} break-words`;
  div.innerHTML = `<span class="text-slate-400">[${time}]</span> <span class="opacity-75">${tag}</span> ${message}`;
  terminalLogs.appendChild(div);
  terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

function updateConnectionStatus(state) {
  if (state === 'ready') connectionStatus.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span><span>Sẵn sàng</span>`;
  else if (state === 'processing') connectionStatus.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span><span class="text-amber-300 font-medium">Đang xử lý</span>`;
  else connectionStatus.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-500"></span><span class="text-slate-400">Chưa kết nối</span>`;
}

function updateProgress(percent, message) {
  progressBar.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;
  if (message) progressStepLabel.textContent = message;
}

function setProcessingState(isProcessing) {
  if (isProcessing) {
    btnStart.disabled = true;
    btnSpinner.classList.remove('hidden');
    btnStartText.textContent = 'Đang xử lý video...';
    progressSection.classList.remove('hidden');
    resultCard.classList.add('hidden');
    updateConnectionStatus('processing');
  } else {
    btnStart.disabled = false;
    btnSpinner.classList.add('hidden');
    btnStartText.textContent = 'Bắt đầu chuyển đổi & bóc phụ đề';
  }
}

function setSubmittingState(isSubmitting, isReRender = false) {
  if (isSubmitting) {
    btnConfirmSrt.disabled = true;
    btnConfirmSrt.innerHTML = `<svg class="animate-spin w-4 h-4 text-white inline-block mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span>Đang tiến hành nhúng phụ đề bằng FFmpeg...</span>`;
  } else {
    btnConfirmSrt.disabled = false;
    btnConfirmSrt.innerHTML = isReRender
      ? `<span>🎬 Cập nhật & Nhúng lại phụ đề</span><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>`
      : `<span>🎬 Xác nhận & Nhúng phụ đề vào Video</span><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>`;
  }
}

// --- Init modules ---
const { syncLiveOverlay } = initPlayer({ previewPlayer, previewVideoWrapper, subOverlay, videoRatioBadge, previewResText,
  getCues: () => cues,
  setLastActiveCueId: (id) => { lastActiveCueId = id; },
  getLastActiveCueId: () => lastActiveCueId,
  cueCardsContainer
});

const { renderCueCards, updateSubOverlayStyle, getIsRawMode } = initEditor({
  cueCardsContainer, srtTextarea, cueCountBadge, btnToggleEditorMode, toggleModeIcon, toggleModeText,
  btnExportSrt, btnExportVtt, btnResetSrt, subColorPicker, subColorVal, subFontSizeSlider, subFontSizeVal,
  subMarginVSlider, subMarginVVal, subOverlay, previewPlayer, appendLog,
  getCues: () => cues,
  setCues: (c) => { cues = c; },
  getOriginalAiSrt: () => originalAiSrt,
  syncLiveOverlay
});

const { connectWebSocket, sendPhase2 } = initPipeline({
  appendLog, updateProgress, setProcessingState, setSubmittingState, updateConnectionStatus,
  getCues: () => cues,
  setCues: (c) => { cues = c; },
  getIsRawMode, renderCueCards, updateSubOverlayStyle, previewPlayer,
  srtEditorSection, srtTextarea, resultCard, finalVideoPlayer, btnDownloadFinalVideo, outputDirPath,
  subColorPicker, subFontSizeSlider, subMarginVSlider, previewVideoWrapper,
  setCurrentTaskId: (id) => { currentTaskId = id; },
  getCurrentTaskId: () => currentTaskId,
  setOriginalAiSrt: (srt) => { originalAiSrt = srt; }
});

initHistoryDrawer();

// --- Init Batch Queue ---
function loadTaskIntoEditor({ taskId, srtContent, videoUrl, filename }) {
  currentTaskId = taskId;
  currentTaskTitle = filename || taskId;
  originalAiSrt = srtContent;
  srtTextarea.value = srtContent;
  cues = parseSRT(srtContent);
  renderCueCards();
  updateSubOverlayStyle();
  if (videoUrl) {
    previewPlayer.src = `${videoUrl}?t=${Date.now()}`;
  }
  setSubmittingState(false, true);
  srtEditorSection.classList.remove('hidden');
  resultCard.classList.add('hidden');
  srtEditorSection.scrollIntoView({ behavior: 'smooth' });
  if (typeof setActiveEditorTaskId === 'function') {
    setActiveEditorTaskId(taskId);
  }
}

const {
  uploadBatchFiles,
  startPolling: startBatchPolling,
  setActiveEditorTaskId,
  getCurrentTasks,
  fetchBatchStatus
} = initBatchQueue({
  appendLog,
  loadTaskIntoEditor,
  subColorPicker,
  subFontSizeSlider,
  subMarginVSlider,
  previewVideoWrapper
});

startBatchPolling();

// --- Workspace Switching ---
function switchWorkspace(tab) {
  currentWorkspaceTab = tab;
  if (tab === 'single') {
    singleWorkflowSection?.classList.remove('hidden');
    batchWorkflowSection?.classList.add('hidden');
    tabBtnSingle?.classList.add('bg-slate-800', 'text-white', 'font-semibold', 'border-slate-700', 'shadow-sm');
    tabBtnSingle?.classList.remove('text-slate-400');
    tabBtnBatch?.classList.remove('bg-slate-800', 'text-white', 'font-semibold', 'border-slate-700', 'shadow-sm');
    tabBtnBatch?.classList.add('text-slate-400');
  } else if (tab === 'batch') {
    batchWorkflowSection?.classList.remove('hidden');
    singleWorkflowSection?.classList.add('hidden');
    tabBtnBatch?.classList.add('bg-slate-800', 'text-white', 'font-semibold', 'border-slate-700', 'shadow-sm');
    tabBtnBatch?.classList.remove('text-slate-400');
    tabBtnSingle?.classList.remove('bg-slate-800', 'text-white', 'font-semibold', 'border-slate-700', 'shadow-sm');
    tabBtnSingle?.classList.add('text-slate-400');
    startBatchPolling();
  }
}

tabBtnSingle?.addEventListener('click', () => switchWorkspace('single'));
tabBtnBatch?.addEventListener('click', () => switchWorkspace('batch'));

// Batch Dropzone Listeners
batchDropzone?.addEventListener('click', () => batchFileInput?.click());
batchDropzone?.addEventListener('dragover', (e) => {
  e.preventDefault();
  batchDropzone.classList.add('border-indigo-500', 'bg-indigo-500/5');
});
batchDropzone?.addEventListener('dragleave', () => {
  batchDropzone.classList.remove('border-indigo-500', 'bg-indigo-500/5');
});
batchDropzone?.addEventListener('drop', (e) => {
  e.preventDefault();
  batchDropzone.classList.remove('border-indigo-500', 'bg-indigo-500/5');
  if (e.dataTransfer.files?.length) {
    uploadBatchFiles(e.dataTransfer.files);
  }
});
batchFileInput?.addEventListener('change', (e) => {
  if (e.target.files?.length) {
    uploadBatchFiles(e.target.files);
  }
});

// --- Initialize Settings Center ---
const { getSettings } = initSettings({
  onSettingsUpdated: (newSettings) => {
    appendLog('Cấu hình hệ thống đã được cập nhật thành công.', 'success');
    if (newSettings?.subtitle_preset) {
      const p = newSettings.subtitle_preset;
      if (p.font_size && subFontSizeSlider) {
        subFontSizeSlider.value = p.font_size;
        if (subFontSizeVal) subFontSizeVal.textContent = `${p.font_size}px`;
      }
      updateSubOverlayStyle();
    }
  }
});

// Quick Navbar button bindings
hwStatusPill?.addEventListener('click', () => openSettingsModal('hardware'));
btnNavOpenFolder?.addEventListener('click', async () => {
  try {
    const s = getSettings();
    const outDir = s?.storage?.output_dir || lastOutputDir || 'outputs';
    const res = await fetch(`/api/open-folder?path=${encodeURIComponent(outDir)}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail);
    }
    appendLog(`Đã mở thư mục lưu trữ: ${outDir}`, 'success');
  } catch (err) {
    appendLog(`Lỗi mở thư mục: ${err.message}`, 'error');
  }
});

// --- Event: pipeline:action_required ---
window.addEventListener('pipeline:action_required', (e) => {
  const data = e.detail;
  const parsed = parseSRT(data.srt_content || '');
  cues = parsed;
  renderCueCards();
  updateSubOverlayStyle();
  if (data.video_url) {
    previewPlayer.src = `${data.video_url}?t=${Date.now()}`;
  }
  srtEditorSection.classList.remove('hidden');
  srtEditorSection.scrollIntoView({ behavior: 'smooth' });
  appendLog(`[Bóc tách hoàn tất] ${data.message}`, 'warn');
});

// --- History events ---
window.addEventListener('history:view', (e) => {
  const { videoUrl, taskId } = e.detail;
  currentTaskId = taskId;
  finalVideoPlayer.src = `${videoUrl}?t=${Date.now()}`;
  btnDownloadFinalVideo.href = videoUrl;
  resultCard.classList.remove('hidden');
  resultCard.scrollIntoView({ behavior: 'smooth' });
});

window.addEventListener('history:edit', async (e) => {
  const { taskId, srtUrl, videoUrl } = e.detail;
  currentTaskId = taskId;
  try {
    const srtRes = await fetch(srtUrl);
    const srtText = await srtRes.text();
    originalAiSrt = srtText;
    srtTextarea.value = srtText;
    cues = parseSRT(srtText);
    renderCueCards();
    updateSubOverlayStyle();
    if (videoUrl) {
      previewPlayer.src = `${videoUrl}?t=${Date.now()}`;
    }
    srtEditorSection.classList.remove('hidden');
    srtEditorSection.scrollIntoView({ behavior: 'smooth' });
    setSubmittingState(false, true);
    appendLog(`Đang chỉnh sửa lại dự án: ${taskId}`, 'warn');
  } catch(err) {
    appendLog(`Lỗi tải dự án: ${err.message}`, 'error');
  }
});

// --- Dropzone ---
dropzone.addEventListener('click', () => videoFileInput.click());
dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('border-indigo-500', 'bg-indigo-500/5');
});
dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('border-indigo-500', 'bg-indigo-500/5');
});
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('border-indigo-500', 'bg-indigo-500/5');
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    if (e.dataTransfer.files.length > 1) {
      switchWorkspace('batch');
      uploadBatchFiles(e.dataTransfer.files);
    } else {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  }
});
videoFileInput.addEventListener('change', (e) => {
  if (e.target.files && e.target.files.length > 0) {
    if (e.target.files.length > 1) {
      switchWorkspace('batch');
      uploadBatchFiles(e.target.files);
    } else {
      handleFileSelect(e.target.files[0]);
    }
  }
});

function handleFileSelect(file) {
  if (!file.type.startsWith('video/') && !file.name.toLowerCase().endsWith('.mp4')) {
    alert('Vui lòng chọn tệp video hợp lệ (.mp4)');
    return;
  }
  selectedFile = file;
  const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = `(${sizeMb} MB)`;
  fileSelectedBadge.classList.remove('hidden');
  appendLog(`Đã chọn: ${file.name} (${sizeMb} MB)`, 'info');
}

// --- Start Pipeline ---
btnStart.addEventListener('click', async () => {
  if (!selectedFile) {
    alert('Vui lòng chọn tệp video trước!');
    videoFileInput.click();
    return;
  }
  setProcessingState(true);
  updateProgress(5, 'Đang tải lên máy chủ...');
  srtEditorSection.classList.add('hidden');
  resultCard.classList.add('hidden');
  appendLog(`Bắt đầu tải: ${selectedFile.name}...`, 'system');
  try {
    const fd = new FormData();
    fd.append('file', selectedFile);
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const e = await res.json();
      throw new Error(e.detail || 'Upload thất bại');
    }
    const { task_id } = await res.json();
    appendLog(`Upload thành công! Task: ${task_id}`, 'success');
    updateProgress(10, 'Video đã lưu. Bắt đầu pipeline...');
    connectWebSocket(task_id);
  } catch(err) {
    appendLog(`Lỗi upload: ${err.message}`, 'error');
    alert(`Lỗi: ${err.message}`);
    setProcessingState(false);
    updateConnectionStatus('ready');
  }
});

// --- Confirm / Re-render ---
btnConfirmSrt.addEventListener('click', async () => {
  if (btnConfirmSrt.disabled) return;
  if (getIsRawMode()) cues = parseSRT(srtTextarea.value);
  if (!cues.length) {
    alert('Nội dung phụ đề không được để trống.');
    return;
  }
  
  const editedSrt = serializeCuesToSRT(cues);
  const previewHeight = previewVideoWrapper.clientHeight || 400;
  const fontPx = parseInt(subFontSizeSlider.value, 10);
  const marginPercent = parseInt(subMarginVSlider.value, 10);
  const assFontSize = Math.max(16, Math.round(fontPx * (1080 / previewHeight)));
  const assMarginV = Math.round(1080 * (marginPercent / 100));
  const subStyle = {
    color_bgr: hexToAssBgr(subColorPicker.value),
    font_size: assFontSize,
    margin_v: assMarginV,
    play_res_y: 1080
  };

  const allBatchTasks = typeof getCurrentTasks === 'function' ? getCurrentTasks() : [];
  const isBatchTask = allBatchTasks.some(t => t.task_id === currentTaskId);

  if (isBatchTask && currentTaskId) {
    setSubmittingState(true);
    appendLog(`Lưu kịch bản và bắt đầu nhúng phụ đề cho "${currentTaskTitle || currentTaskId}"...`, 'system');
    try {
      // 1. Lưu SRT đã sửa
      await fetch(`/api/batch/task/${currentTaskId}/save-srt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ srt_content: editedSrt })
      });

      // 2. Kích hoạt lệnh nhúng (non-blocking)
      const res = await fetch('/api/batch/render-task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: currentTaskId, sub_style: subStyle })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi gửi lệnh nhúng');

      appendLog(`Đã gửi lệnh nhúng phụ đề cho "${currentTaskTitle || currentTaskId}"! Video đang được xử lý trong danh sách hàng đợi.`, 'success');
      
      if (typeof fetchBatchStatus === 'function') fetchBatchStatus();

      // Mở khóa nút bấm để user có thể tiếp tục thao tác
      setSubmittingState(false, true);

      // Gợi ý video tiếp theo nếu có video chờ duyệt
      const nextWaiting = allBatchTasks.find(t => t.status === 'waiting_review' && t.task_id !== currentTaskId);
      if (nextWaiting) {
        appendLog(`Gợi ý: Video "${nextWaiting.filename}" đang chờ duyệt kịch bản. Bạn có thể bấm "Duyệt & Xem trước" ở trên để chỉnh sửa ngay!`, 'info');
      }
    } catch(err) {
      setSubmittingState(false);
      appendLog(`Lỗi: ${err.message}`, 'error');
      alert(`Đã xảy ra lỗi: ${err.message}`);
    }
  } else {
    // Single upload WebSocket flow
    setSubmittingState(true);
    appendLog(`Nhúng phụ đề (${cues.length} câu) - Font: ${assFontSize}px, Lề: ${marginPercent}%...`, 'system');
    updateProgress(80, 'Đang nhúng phụ đề bằng FFmpeg...');
    try {
      await sendPhase2(editedSrt, subStyle);
    } catch(err) {
      setSubmittingState(false);
      appendLog(`Lỗi: ${err.message}`, 'error');
      alert(`Đã xảy ra lỗi: ${err.message}`);
      setProcessingState(false);
    }
  }
});

// --- Back to Editor ---
btnBackToEditor.addEventListener('click', () => {
  srtEditorSection.classList.remove('hidden');
  srtEditorSection.scrollIntoView({ behavior: 'smooth' });
  setSubmittingState(false, true);
  appendLog('Chế độ chỉnh sửa lại: Sửa xong bấm "Cập nhật & Nhúng lại".', 'info');
});

// --- Open Folder ---
btnOpenFolder.addEventListener('click', async () => {
  if (!lastOutputDir) return;
  try {
    const res = await fetch(`/api/open-folder?path=${encodeURIComponent(lastOutputDir)}`);
    if (!res.ok) throw new Error((await res.json()).detail);
    appendLog(`Đã mở thư mục: ${lastOutputDir}`, 'success');
  } catch(err) {
    appendLog(`Lỗi: ${err.message}`, 'error');
  }
});

// --- Clear Logs ---
btnClearLog.addEventListener('click', () => {
  terminalLogs.innerHTML = '';
  appendLog('Đã xóa console.', 'system');
});
