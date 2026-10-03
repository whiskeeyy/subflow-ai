// frontend/js/batch.js — Batch Processing & Task Queue
import { parseSRT, hexToAssBgr, serializeCuesToSRT } from './utils.js';

export function initBatchQueue({
  appendLog,
  loadTaskIntoEditor,
  subColorPicker,
  subFontSizeSlider,
  subMarginVSlider,
  previewVideoWrapper
}) {
  const batchSection = document.getElementById('batchSection');
  const batchQueueList = document.getElementById('batchQueueList');
  const batchCountBadge = document.getElementById('batchCountBadge');
  const btnBatchRenderAll = document.getElementById('btnBatchRenderAll');

  let pollInterval = null;
  let currentTasks = [];

  function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(fetchBatchStatus, 2500);
    fetchBatchStatus();
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  async function fetchBatchStatus() {
    try {
      const res = await fetch('/api/batch/status');
      if (!res.ok) return;
      currentTasks = await res.json();
      renderQueue(currentTasks);

      // Check if all tasks done or error to slow/stop polling
      const isAnyRunning = currentTasks.some(t => t.status === 'pending' || t.status === 'processing_phase1' || t.status === 'rendering');
      if (!isAnyRunning && currentTasks.length > 0) {
        // All finished or waiting review
      }
    } catch (e) {
      console.error('Error fetching batch status:', e);
    }
  }

  function renderQueue(tasks) {
    if (!tasks || tasks.length === 0) {
      batchSection.classList.add('hidden');
      return;
    }

    batchSection.classList.remove('hidden');
    batchCountBadge.textContent = `${tasks.length} video trong hàng đợi`;

    // Count how many waiting review
    const readyCount = tasks.filter(t => t.status === 'waiting_review').length;
    btnBatchRenderAll.disabled = readyCount === 0;
    btnBatchRenderAll.textContent = readyCount > 0 
      ? `🎬 Render hàng loạt (${readyCount} video đã duyệt)`
      : '🎬 Render hàng loạt (0 video sẵn sàng)';

    batchQueueList.innerHTML = '';
    const fragment = document.createDocumentFragment();

    tasks.forEach(task => {
      const card = document.createElement('div');
      card.className = 'batch-card bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 transition-all flex flex-col gap-2.5';
      card.dataset.taskId = task.task_id;

      let statusBadge = '';
      if (task.status === 'pending') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span><span>Chờ xếp hàng</span></span>`;
      } else if (task.status === 'processing_phase1') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span><span>Đang xử lý AI (${task.percent}%)</span></span>`;
      } else if (task.status === 'waiting_review') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"><span class="w-1.5 h-1.5 rounded-full bg-indigo-400"></span><span>Sẵn sàng duyệt kịch bản</span></span>`;
      } else if (task.status === 'rendering') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30"><span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-spin"></span><span>Đang nhúng phụ đề...</span></span>`;
      } else if (task.status === 'done') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span>Hoàn thành 100%</span></span>`;
      } else if (task.status === 'error') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-red-500/20 text-red-400 border border-red-500/30"><span>Lỗi xử lý</span></span>`;
      }

      card.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2.5 min-w-0">
            <div class="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
            </div>
            <div class="min-w-0">
              <div class="text-xs font-semibold text-slate-200 truncate max-w-[280px]" title="${task.filename}">${task.filename}</div>
              <div class="text-[10px] text-slate-500 font-mono">${task.task_id}</div>
            </div>
          </div>
          <div>${statusBadge}</div>
        </div>

        <!-- Progress message if running -->
        ${(task.status === 'processing_phase1' || task.status === 'rendering') ? `
          <div class="space-y-1">
            <div class="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
              <div class="bg-gradient-to-r from-indigo-500 to-teal-400 h-1.5 rounded-full transition-all duration-300" style="width: ${task.percent}%"></div>
            </div>
            <div class="text-[10px] text-slate-400 truncate">${task.message || ''}</div>
          </div>
        ` : ''}

        <!-- Actions -->
        <div class="flex items-center justify-between pt-1 border-t border-slate-800/80 text-xs">
          <span class="text-[10px] text-slate-500">${task.message || ''}</span>
          <div class="flex items-center space-x-2">
            ${task.status === 'waiting_review' ? `
              <button type="button" class="btn-review-task px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-sm transition flex items-center space-x-1" data-task-id="${task.task_id}">
                <span>📝 Duyệt & Xem trước</span>
              </button>
            ` : ''}
            ${task.status === 'done' ? `
              <a href="${task.final_video_url}" target="_blank" class="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 font-medium text-xs transition flex items-center space-x-1">
                <span>▶ Xem</span>
              </a>
              <a href="${task.final_video_url}" download class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition flex items-center space-x-1">
                <span>📥 Tải</span>
              </a>
            ` : ''}
          </div>
        </div>
      `;

      // Event: Review task in editor
      card.querySelector('.btn-review-task')?.addEventListener('click', async (e) => {
        const tid = e.currentTarget.dataset.taskId;
        await openTaskInEditor(tid);
      });

      fragment.appendChild(card);
    });

    batchQueueList.appendChild(fragment);
  }

  async function openTaskInEditor(taskId) {
    try {
      appendLog(`Đang tải dữ liệu kịch bản cho tác vụ: ${taskId}...`, 'system');
      const res = await fetch(`/api/batch/task/${taskId}`);
      if (!res.ok) throw new Error('Không thể tải thông tin tác vụ');
      const data = await res.json();
      loadTaskIntoEditor({
        taskId: taskId,
        srtContent: data.srt_content || '',
        videoUrl: data.video_url,
        filename: data.task?.filename || taskId
      });
      appendLog(`Đã nạp video ${data.task?.filename || taskId} vào khung xem trước & thẻ phụ đề.`, 'success');
    } catch (e) {
      appendLog(`Lỗi mở tác vụ: ${e.message}`, 'error');
      alert(`Lỗi: ${e.message}`);
    }
  }

  // Batch render all reviewed
  btnBatchRenderAll?.addEventListener('click', async () => {
    const readyTasks = currentTasks.filter(t => t.status === 'waiting_review');
    if (!readyTasks.length) {
      alert('Không có video nào ở trạng thái chờ duyệt kịch bản.');
      return;
    }

    if (!confirm(`Bạn có chắc muốn render hàng loạt cho ${readyTasks.length} video đã duyệt kịch bản không?`)) {
      return;
    }

    btnBatchRenderAll.disabled = true;
    btnBatchRenderAll.textContent = '⏳ Đang khởi tạo render hàng loạt...';
    appendLog(`Bắt đầu render hàng loạt cho ${readyTasks.length} video...`, 'system');

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

    try {
      const res = await fetch('/api/batch/render-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sub_style: subStyle })
      });
      const data = await res.json();
      appendLog(`Hoàn thành lệnh render hàng loạt: ${data.rendered_count} video đã render!`, 'success');
      fetchBatchStatus();
      if (window.refreshHistory) window.refreshHistory();
    } catch (e) {
      appendLog(`Lỗi render hàng loạt: ${e.message}`, 'error');
      alert(`Lỗi render: ${e.message}`);
    } finally {
      btnBatchRenderAll.disabled = false;
    }
  });

  async function uploadBatchFiles(files) {
    appendLog(`Bắt đầu tải lên ${files.length} video vào hàng đợi ngầm...`, 'system');
    batchSection.classList.remove('hidden');

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const res = await fetch('/api/batch/upload', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Lỗi tải lên hàng loạt');
      }
      const data = await res.json();
      appendLog(`Đã tải lên & xếp hàng thành công ${data.enqueued_count} video!`, 'success');
      startPolling();
    } catch (e) {
      appendLog(`Lỗi tải lên hàng loạt: ${e.message}`, 'error');
      alert(`Lỗi: ${e.message}`);
    }
  }

  return {
    uploadBatchFiles,
    startPolling,
    stopPolling,
    fetchBatchStatus
  };
}
