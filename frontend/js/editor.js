// frontend/js/editor.js
import { secondsToDisplay, secondsToSRT, serializeCuesToSRT, serializeCuesToVTT, parseSRT, downloadBlob } from './utils.js';

export function initEditor({ cueCardsContainer, srtTextarea, cueCountBadge, btnToggleEditorMode, toggleModeIcon, toggleModeText, btnExportSrt, btnExportVtt, btnResetSrt, subColorPicker, subColorVal, subFontSizeSlider, subFontSizeVal, subMarginVSlider, subMarginVVal, subOverlay, previewPlayer, appendLog, getCues, setCues, getOriginalAiSrt, syncLiveOverlay }) {

  let isRawMode = false;

  function autoResizeTextarea(el) {
    el.style.height = 'auto';
    el.style.height = (el.scrollHeight + 2) + 'px';
  }

  function renderCueCards() {
    const cues = getCues();
    cueCountBadge.textContent = `${cues.length} câu phụ đề`;
    if (cues.length === 0) {
      cueCardsContainer.innerHTML = `<div class="text-center py-12 text-slate-500 text-xs">Chưa có câu phụ đề nào.</div>`;
      return;
    }
    cueCardsContainer.innerHTML = '';
    const fragment = document.createDocumentFragment();
    cues.forEach((cue, index) => {
      const isLast = index === cues.length - 1;
      const card = document.createElement('div');
      card.className = 'cue-card group relative bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3 transition-all flex flex-col gap-2 cursor-pointer';
      card.dataset.id = cue.id;
      card.dataset.index = index;
      card.innerHTML = `
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center space-x-2">
            <span class="cue-idx font-mono font-bold text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">#${index + 1}</span>
            <button type="button" class="btn-jump flex items-center space-x-1 font-mono text-[11px] text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 px-2 py-0.5 rounded transition" title="Nhảy đến mốc thời gian">
              <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
              <span>${secondsToDisplay(cue.start)} → ${secondsToDisplay(cue.end)}</span>
            </button>
          </div>
          <div class="flex items-center space-x-1.5 opacity-80 group-hover:opacity-100 transition">
            <button type="button" class="btn-split px-2 py-0.5 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition" title="Tách câu">✂️ Tách</button>
            ${!isLast ? '<button type="button" class="btn-merge px-2 py-0.5 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition" title="Gộp câu">🔗 Gộp</button>' : ''}
          </div>
        </div>
        <textarea rows="1" class="cue-text w-full bg-slate-950/70 border border-slate-800 focus:border-indigo-500 focus:bg-slate-950 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-sans focus:outline-none transition resize-none leading-relaxed" placeholder="Nhập nội dung phụ đề...">${cue.text}</textarea>
      `;
      card.addEventListener('click', (e) => {
        if (e.target.closest('.btn-split') || e.target.closest('.btn-merge') || e.target.closest('.cue-text')) return;
        previewPlayer.currentTime = cue.start;
        previewPlayer.play().catch(() => {});
      });
      card.querySelector('.btn-jump').addEventListener('click', (e) => {
        e.stopPropagation();
        previewPlayer.currentTime = cue.start;
        previewPlayer.play().catch(() => {});
      });
      const textarea = card.querySelector('.cue-text');
      textarea.addEventListener('input', (e) => {
        cue.text = e.target.value;
        if (previewPlayer.currentTime >= cue.start && previewPlayer.currentTime <= cue.end)
          subOverlay.textContent = cue.text;
        autoResizeTextarea(textarea);
      });
      card.querySelector('.btn-split').addEventListener('click', (e) => { e.stopPropagation(); splitCue(index); });
      card.querySelector('.btn-merge')?.addEventListener('click', (e) => { e.stopPropagation(); mergeCue(index); });
      fragment.appendChild(card);
    });
    cueCardsContainer.appendChild(fragment);
    setTimeout(() => cueCardsContainer.querySelectorAll('.cue-text').forEach(autoResizeTextarea), 50);
  }

  function splitCue(index) {
    const cues = getCues();
    const cue = cues[index];
    const mid = (cue.start + cue.end) / 2;
    const words = cue.text.trim().split(/\s+/);
    let text1 = cue.text, text2 = '...';
    if (words.length > 1) {
      const midWord = Math.ceil(words.length / 2);
      text1 = words.slice(0, midWord).join(' ');
      text2 = words.slice(midWord).join(' ');
    }
    const originalEnd = cue.end;
    cue.end = mid; cue.endTimeStr = secondsToSRT(mid); cue.text = text1;
    cues.splice(index + 1, 0, { id: 0, start: mid, end: originalEnd, startTimeStr: secondsToSRT(mid), endTimeStr: secondsToSRT(originalEnd), text: text2 });
    cues.forEach((c, idx) => c.id = idx + 1);
    renderCueCards(); syncLiveOverlay();
    appendLog(`Đã tách câu #${index + 1} thành 2 mốc.`, 'info');
  }

  function mergeCue(index) {
    const cues = getCues();
    if (index >= cues.length - 1) return;
    const curr = cues[index], next = cues[index + 1];
    curr.text = (curr.text.trim() + ' ' + next.text.trim()).trim();
    curr.end = next.end; curr.endTimeStr = next.endTimeStr;
    cues.splice(index + 1, 1);
    cues.forEach((c, idx) => c.id = idx + 1);
    renderCueCards(); syncLiveOverlay();
    appendLog(`Đã gộp câu #${index + 1} với câu tiếp theo.`, 'info');
  }

  function updateSubOverlayStyle() {
    const color = subColorPicker.value;
    const fontSize = parseInt(subFontSizeSlider.value, 10);
    const marginPercent = parseInt(subMarginVSlider.value, 10);
    subColorVal.textContent = color.toUpperCase();
    subFontSizeVal.textContent = `${fontSize}px`;
    subMarginVVal.textContent = `${marginPercent}%`;
    subOverlay.style.color = color;
    subOverlay.style.fontSize = `${fontSize}px`;
    subOverlay.style.bottom = `${marginPercent}%`;
  }

  subColorPicker.addEventListener('input', updateSubOverlayStyle);
  subFontSizeSlider.addEventListener('input', updateSubOverlayStyle);
  subMarginVSlider.addEventListener('input', updateSubOverlayStyle);

  btnToggleEditorMode.addEventListener('click', () => {
    isRawMode = !isRawMode;
    if (isRawMode) {
      srtTextarea.value = serializeCuesToSRT(getCues());
      cueCardsContainer.classList.add('hidden');
      srtTextarea.classList.remove('hidden');
      toggleModeIcon.textContent = '🃏';
      toggleModeText.textContent = 'Chế độ thẻ (Cards)';
    } else {
      setCues(parseSRT(srtTextarea.value));
      renderCueCards();
      srtTextarea.classList.add('hidden');
      cueCardsContainer.classList.remove('hidden');
      toggleModeIcon.textContent = '📄';
      toggleModeText.textContent = 'Chế độ mã nguồn (Raw)';
    }
  });

  btnExportSrt.addEventListener('click', () => {
    if (isRawMode) setCues(parseSRT(srtTextarea.value));
    if (!getCues().length) { alert('Chưa có phụ đề!'); return; }
    downloadBlob(serializeCuesToSRT(getCues()), 'subtitles.srt', 'text/plain;charset=utf-8');
    appendLog('Đã tải .srt thành công.', 'success');
  });

  btnExportVtt.addEventListener('click', () => {
    if (isRawMode) setCues(parseSRT(srtTextarea.value));
    if (!getCues().length) { alert('Chưa có phụ đề!'); return; }
    downloadBlob(serializeCuesToVTT(getCues()), 'subtitles.vtt', 'text/vtt;charset=utf-8');
    appendLog('Đã tải .vtt thành công.', 'success');
  });

  btnResetSrt.addEventListener('click', () => {
    const orig = getOriginalAiSrt();
    if (orig) { setCues(parseSRT(orig)); renderCueCards(); srtTextarea.value = orig; syncLiveOverlay(); appendLog('Đã khôi phục phụ đề gốc.', 'info'); }
  });

  return { renderCueCards, updateSubOverlayStyle, getIsRawMode: () => isRawMode };
}
