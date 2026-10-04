// frontend/js/pipeline.js
import { hexToAssBgr, serializeCuesToSRT } from './utils.js';

export function initPipeline({ appendLog, updateProgress, setProcessingState, setSubmittingState, updateConnectionStatus, getCues, setCues, getIsRawMode, renderCueCards, updateSubOverlayStyle, previewPlayer, srtEditorSection, srtTextarea, resultCard, finalVideoPlayer, btnDownloadFinalVideo, outputDirPath, subColorPicker, subFontSizeSlider, subMarginVSlider, previewVideoWrapper, setCurrentTaskId, getCurrentTaskId, setOriginalAiSrt }) {

  let socket = null;

  function connectWebSocket(taskId) {
    setCurrentTaskId(taskId);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    if (socket) try { socket.close(); } catch(e) {}
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/process`);
    socket.onopen = () => {
      updateConnectionStatus('processing');
      appendLog('Đã kết nối WebSocket. Bắt đầu bóc tách âm thanh & dịch thuật...', 'system');
      socket.send(JSON.stringify({ task_id: taskId }));
    };
    socket.onmessage = (event) => {
      try { handleWsMessage(JSON.parse(event.data)); }
      catch(e) { appendLog(`Server: ${event.data}`, 'info'); }
    };
    socket.onerror = () => { appendLog('Lỗi kết nối WebSocket.', 'error'); setProcessingState(false); updateConnectionStatus('disconnected'); };
    socket.onclose = () => { appendLog('Kết nối WebSocket đã đóng.', 'info'); updateConnectionStatus('ready'); };
  }

  function handleWsMessage(data) {
    const { status } = data;
    if (status === 'PROGRESS') {
      updateProgress(data.percent, data.message);
      appendLog(data.message, 'info');
    } else if (status === 'ACTION_REQUIRED') {
      updateProgress(75, 'Chờ duyệt kịch bản & xem trước video...');
      if (data.task_id) setCurrentTaskId(data.task_id);
      setOriginalAiSrt(data.srt_content || '');
      srtTextarea.value = data.srt_content || '';
      setCues([]); // will be set by renderCueCards
      window.dispatchEvent(new CustomEvent('pipeline:action_required', { detail: data }));
    } else if (status === 'SUCCESS') {
      updateProgress(100, 'Hoàn thành nhúng phụ đề vào video!');
      setProcessingState(false);
      setSubmittingState(false, true);
      if (data.task_id) setCurrentTaskId(data.task_id);
      srtEditorSection.classList.add('hidden');
      try { previewPlayer.pause(); } catch(e) {}
      outputDirPath.textContent = data.output_dir;
      const videoSrc = data.video_url || data.relative_paths?.final_video;
      if (videoSrc) { finalVideoPlayer.src = videoSrc + `?t=${Date.now()}`; btnDownloadFinalVideo.href = videoSrc; }
      resultCard.classList.remove('hidden');
      resultCard.scrollIntoView({ behavior: 'smooth' });
      appendLog(data.message, 'success');
      if (window.refreshHistory) window.refreshHistory();
    } else if (status === 'ERROR') {
      setProcessingState(false);
      setSubmittingState(false);
      appendLog(`Lỗi xử lý: ${data.message}`, 'error');
      alert(`Đã xảy ra lỗi: ${data.message}`);
    }
  }

  async function sendPhase2(editedSrt, subStyle) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: 'RESUME_WITH_SCRIPT', edited_srt: editedSrt, sub_style: subStyle }));
    } else {
      const res = await fetch('/api/re-render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: getCurrentTaskId(), edited_srt: editedSrt, sub_style: subStyle })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi render');
      handleWsMessage(data);
    }
  }

  return { connectWebSocket, sendPhase2 };
}
