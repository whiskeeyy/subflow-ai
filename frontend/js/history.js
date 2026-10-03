// frontend/js/history.js
// Project History Drawer - slides from the right

export function initHistoryDrawer() {
  const drawer = document.getElementById('historyDrawer');
  const overlay = document.getElementById('historyOverlay');
  const btnToggle = document.getElementById('btnToggleHistory');
  const btnClose = document.getElementById('btnCloseHistory');
  const historyList = document.getElementById('historyList');
  const historySearch = document.getElementById('historySearch');

  let allItems = [];

  function openDrawer() {
    drawer.classList.add('open');
    overlay.classList.add('open');
    loadHistory();
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    overlay.classList.remove('open');
  }

  btnToggle?.addEventListener('click', openDrawer);
  btnClose?.addEventListener('click', closeDrawer);
  overlay?.addEventListener('click', closeDrawer);

  historySearch?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    renderHistoryItems(q ? allItems.filter(i => i.filename.toLowerCase().includes(q)) : allItems);
  });

  async function loadHistory() {
    historyList.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">Đang tải lịch sử...</div>`;
    try {
      const res = await fetch('/api/history');
      if (!res.ok) throw new Error('Failed to load history');
      allItems = await res.json();
      renderHistoryItems(allItems);
    } catch (e) {
      historyList.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">Không có lịch sử dự án</div>`;
    }
  }

  function renderHistoryItems(items) {
    if (!items.length) {
      historyList.innerHTML = `<div class="text-center py-12 text-slate-500 text-xs space-y-2">
        <div class="text-2xl">📭</div>
        <div>Chưa có dự án nào</div>
      </div>`;
      return;
    }

    // Group by date
    const grouped = {};
    items.forEach(item => {
      const date = item.date || 'Hôm nay';
      if (!grouped[date]) grouped[date] = [];
      grouped[date].push(item);
    });

    historyList.innerHTML = '';
    for (const [date, dateItems] of Object.entries(grouped)) {
      const section = document.createElement('div');
      section.className = 'space-y-1';
      section.innerHTML = `<div class="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">${date}</div>`;

      dateItems.forEach(item => {
        const el = document.createElement('div');
        el.className = 'history-item px-3 py-2.5 rounded-lg mx-1 cursor-pointer space-y-1';
        const statusColor = item.status === 'done' ? 'bg-emerald-500' : item.status === 'processing' ? 'bg-amber-400 animate-pulse' : 'bg-slate-500';
        const statusLabel = item.status === 'done' ? 'Hoàn thành' : item.status === 'processing' ? 'Đang xử lý' : 'Chờ';

        el.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-slate-200 truncate max-w-[200px]" title="${item.filename}">${item.filename}</span>
            <span class="flex items-center space-x-1 ml-2 shrink-0">
              <span class="w-1.5 h-1.5 rounded-full ${statusColor}"></span>
              <span class="text-[10px] text-slate-400">${statusLabel}</span>
            </span>
          </div>
          <div class="flex items-center justify-between text-[10px] text-slate-500">
            <span>${item.time || ''}</span>
            <div class="flex items-center space-x-1.5">
              ${item.status === 'done' ? `
                <button class="btn-view-history text-[10px] text-indigo-400 hover:text-indigo-300 px-1.5 py-0.5 rounded bg-indigo-500/10 hover:bg-indigo-500/20 transition"
                  data-task-id="${item.task_id}" data-video-url="${item.final_video_url}">
                  ▶ Xem lại
                </button>
                <button class="btn-edit-history text-[10px] text-amber-400 hover:text-amber-300 px-1.5 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500/20 transition"
                  data-task-id="${item.task_id}" data-srt-url="${item.srt_url}" data-video-url="${item.video_url}">
                  ✏ Chỉnh sửa
                </button>
              ` : ''}
            </div>
          </div>
        `;

        // View final video
        el.querySelector('.btn-view-history')?.addEventListener('click', (e) => {
          e.stopPropagation();
          const videoUrl = e.currentTarget.dataset.videoUrl;
          closeDrawer();
          window.dispatchEvent(new CustomEvent('history:view', { detail: { videoUrl, taskId: e.currentTarget.dataset.taskId } }));
        });

        // Re-open for editing
        el.querySelector('.btn-edit-history')?.addEventListener('click', async (e) => {
          e.stopPropagation();
          const { taskId, srtUrl, videoUrl } = e.currentTarget.dataset;
          closeDrawer();
          window.dispatchEvent(new CustomEvent('history:edit', { detail: { taskId, srtUrl, videoUrl } }));
        });

        section.appendChild(el);
      });

      historyList.appendChild(section);
    }
  }

  // Refresh history from outside
  window.refreshHistory = loadHistory;
}
