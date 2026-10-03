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
  let activeEditorTaskId = null;
  const completedTaskIds = new Set();

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

      // Check newly completed tasks to notify without interrupting active editor
      currentTasks.forEach(t => {
        if (t.status === 'done' && !completedTaskIds.has(t.task_id)) {
          completedTaskIds.add(t.task_id);
          appendLog(`🎉 Video "${t.filename}" đã nhúng phụ đề hoàn tất!`, 'success');
          if (window.refreshHistory) window.refreshHistory();
        }
      });

      renderQueue(currentTasks);
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
      ? `🎬 Nhúng hàng loạt (${readyCount} video đã duyệt)`
      : '🎬 Nhúng hàng loạt (0 video sẵn sàng)';

    batchQueueList.innerHTML = '';
    const fragment = document.createDocumentFragment();

    tasks.forEach(task => {
      const isActive = (task.task_id === activeEditorTaskId);
      const card = document.createElement('div');
      card.className = `batch-card bg-slate-900 border rounded-xl p-4 transition-all flex flex-col gap-2.5 ${
        isActive 
          ? 'border-indigo-500/80 bg-slate-900/95 ring-1 ring-indigo-500/40 shadow-lg shadow-indigo-500/10' 
          : 'border-slate-800 hover:border-slate-700'
      }`;
      card.dataset.taskId = task.task_id;

      let statusBadge = '';
      if (task.status === 'pending') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span><span>Chờ xếp hàng</span></span>`;
      } else if (task.status === 'processing' || task.status === 'processing_phase1') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span><span>Đang xử lý AI (${task.percent}%)</span></span>`;
      } else if (task.status === 'waiting_review') {
        if (isActive) {
          statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"><span class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span><span>✏️ Đang chỉnh sửa</span></span>`;
        } else {
          statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"><span class="w-1.5 h-1.5 rounded-full bg-indigo-400"></span><span>Chờ duyệt kịch bản</span></span>`;
        }
      } else if (task.status === 'rendering') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30"><svg class="w-3 h-3 text-purple-400 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span>Đang nhúng phụ đề...</span></span>`;
      } else if (task.status === 'done') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span>Hoàn thành 100%</span></span>`;
      } else if (task.status === 'error') {
        statusBadge = `<span class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-red-500/20 text-red-400 border border-red-500/30"><span>Lỗi xử lý</span></span>`;
      }

      const isRunning = (task.status === 'processing' || task.status === 'processing_phase1' || task.status === 'rendering');

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

        <!-- Progress bar if running -->
        ${isRunning ? `
          <div class="space-y-1">
            <div class="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
              <div class="bg-gradient-to-r from-indigo-500 to-teal-400 h-1.5 rounded-full transition-all duration-300" style="width: ${task.percent}%"></div>
            </div>
            <div class="text-[10px] text-slate-400 truncate">${task.message || ''}</div>
          </div>
        ` : ''}

        <!-- Actions -->
        <div class="flex items-center justify-between pt-1 border-t border-slate-800/80 text-xs">
          <span class="text-[10px] text-slate-500 truncate max-w-[220px]">${task.message || ''}</span>
          <div class="flex items-center space-x-2 shrink-0">
            ${task.status === 'waiting_review' ? `
              ${isActive ? `
                <span class="px-2.5 py-1 rounded-lg bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 font-medium text-[11px] flex items-center space-x-1 select-none">
                  <span>👁️ Đang mở biên tập</span>
                </span>
              ` : `
                <button type="button" class="btn-review-task px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-sm transition flex items-center space-x-1" data-task-id="${task.task_id}">
                  <span>📝 Duyệt & Xem trước</span>
                </button>
              `}
            ` : ''}
            ${task.status === 'rendering' ? `
              <button type="button" class="btn-review-task px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-purple-300 border border-purple-500/30 text-xs transition" data-task-id="${task.task_id}" title="Xem lại nội dung trong khi đang nhúng">
                <span>👁️ Xem kịch bản</span>
              </button>
            ` : ''}
            ${task.status === 'done' ? `
              <a href="${task.final_video_url}" target="_blank" class="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 font-medium text-xs transition flex items-center space-x-1">
                <span>▶ Xem</span>
              </a>
              <a href="${task.final_video_url}" download class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition flex items-center space-x-1">
                <span>📥 Tải</span>
              </a>
              <button type="button" class="btn-review-task px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 text-[11px] transition" data-task-id="${task.task_id}" title="Mở ra sửa lại phụ đề">
                <span>✏️ Sửa</span>
              </button>
            ` : ''}
          </div>
        </div>
      `;

      // Event: Review task in editor
      card.querySelectorAll('.btn-review-task').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const tid = e.currentTarget.dataset.taskId;
          await openTaskInEditor(tid);
        });
      });

      fragment.appendChild(card);
    });

    batchQueueList.appendChild(fragment);
  }

  async function openTaskInEditor(taskId) {
    try {
      appendLog(`Đang tải dữ liệu kịch bản: ${taskId}...`, 'system');
      const res = await fetch(`/api/batch/task/${taskId}`);
      if (!res.ok) throw new Error('Không thể tải thông tin tác vụ');
      const data = await res.json();
      activeEditorTaskId = taskId;
      renderQueue(currentTasks);

      loadTaskIntoEditor({
        taskId: taskId,
        srtContent: data.srt_content || '',
        videoUrl: data.video_url,
        filename: data.task?.filename || taskId
      });
      appendLog(`Đã nạp video "${data.task?.filename || taskId}" vào trình biên tập.`, 'success');
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

    if (!confirm(`Bạn có chắc muốn nhúng hàng loạt cho ${readyTasks.length} video đã duyệt kịch bản không?`)) {
      return;
    }

    btnBatchRenderAll.disabled = true;
    btnBatchRenderAll.textContent = '⏳ Đang khởi tạo nhúng hàng loạt...';
    appendLog(`Bắt đầu nhúng hàng loạt cho ${readyTasks.length} video...`, 'system');

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
      appendLog(`Lệnh nhúng hàng loạt đã được gửi: ${data.rendered_count} video đang được xử lý!`, 'success');
      fetchBatchStatus();
      if (window.refreshHistory) window.refreshHistory();
    } catch (e) {
      appendLog(`Lỗi nhúng hàng loạt: ${e.message}`, 'error');
      alert(`Lỗi: ${e.message}`);
    } finally {
      btnBatchRenderAll.disabled = false;
    }
  });

  async function uploadBatchFiles(files) {
    appendLog(`Bắt đầu tải lên ${files.length} video vào hàng đợi...`, 'system');
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
    fetchBatchStatus,
    setActiveEditorTaskId: (id) => {
      activeEditorTaskId = id;
      renderQueue(currentTasks);
    },
    getActiveEditorTaskId: () => activeEditorTaskId,
    getCurrentTasks: () => currentTasks
  };
}
