// frontend/js/pipeline.js
import { hexToAssBgr, serializeCuesToSRT } from './utils.js';
import { showToast, showErrorModal } from './ui_dialog.js';

export function initPipeline({
  appendLog,
  updateProgress,
  setProcessingState,
  setSubmittingState,
  updateConnectionStatus,
  getCues,
  setCues,
  getIsRawMode,
  renderCueCards,
  updateSubOverlayStyle,
  previewPlayer,
  srtEditorSection,
  srtTextarea,
  resultCard,
  finalVideoPlayer,
  btnDownloadFinalVideo,
  outputDirPath,
  subColorPicker,
  subFontSizeSlider,
  subMarginVSlider,
  previewVideoWrapper,
  setCurrentTaskId,
  getCurrentTaskId,
  setOriginalAiSrt
}) {

  let socket = null;

  function connectWebSocket(taskId) {
    setCurrentTaskId(taskId);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    if (socket) {
      try { socket.close(); } catch(e) {}
    }
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/process`);

    socket.onopen = () => {
      updateConnectionStatus('processing');
      appendLog('Đã kết nối WebSocket. Bắt đầu bóc tách âm thanh & dịch thuật...', 'system');
      socket.send(JSON.stringify({ task_id: taskId }));
    };

    socket.onmessage = (event) => {
      try {
        handleWsMessage(JSON.parse(event.data));
      } catch(e) {
        appendLog(`Server: ${event.data}`, 'info');
      }
    };

    socket.onerror = () => {
      appendLog('Lỗi kết nối WebSocket.', 'error');
      setProcessingState(false);
      setSubmittingState(false);
      updateConnectionStatus('disconnected');
      showErrorModal({
        title: 'Mất kết nối WebSocket',
        message: 'Đường truyền dữ liệu với máy chủ nền bị gián đoạn.',
        suggestion: 'Hệ thống đã tự động đưa trạng thái về an toàn. Vui lòng bấm "Bắt đầu" để thử lại.'
      });
    };

    socket.onclose = () => {
      appendLog('Kết nối WebSocket đã đóng.', 'info');
      updateConnectionStatus('ready');
    };
  }

  function handleWsMessage(data) {
    const { status } = data;

    if (status === 'PROGRESS') {
      updateProgress(data.percent, data.message, data.live_text, data.metrics);
      if (data.message) appendLog(data.message, 'info');
    } else if (status === 'ACTION_REQUIRED') {
      updateProgress(80, 'Chờ duyệt kịch bản & xem trước video...', '', null);
      if (data.task_id) setCurrentTaskId(data.task_id);
      setOriginalAiSrt(data.srt_content || '');
      srtTextarea.value = data.srt_content || '';
      setCues([]); // will be initialized by renderCueCards
      window.dispatchEvent(new CustomEvent('pipeline:action_required', { detail: data }));
    } else if (status === 'SUCCESS') {
      updateProgress(100, 'Hoàn thành nhúng phụ đề vào video!', '', null);
      setProcessingState(false);
      setSubmittingState(false, true);
      if (data.task_id) setCurrentTaskId(data.task_id);
      srtEditorSection.classList.add('hidden');
      try { previewPlayer.pause(); } catch(e) {}
      outputDirPath.textContent = data.output_dir;
      const videoSrc = data.video_url || data.relative_paths?.final_video;
      if (videoSrc) {
        finalVideoPlayer.src = videoSrc + `?t=${Date.now()}`;
        btnDownloadFinalVideo.href = videoSrc;
      }
      resultCard.classList.remove('hidden');
      resultCard.scrollIntoView({ behavior: 'smooth' });
      appendLog(data.message, 'success');
      showToast('Đã hoàn thành nhúng phụ đề vào video!', 'success');
      if (window.refreshHistory) window.refreshHistory();
    } else if (status === 'CANCELLED') {
      setProcessingState(false);
      setSubmittingState(false);
      updateProgress(0, 'Tác vụ đã bị hủy bỏ.', '', null);
      appendLog(data.message || 'Đã hủy tác vụ thành công.', 'warn');
      showToast(data.message || 'Đã hủy tác vụ thành công.', 'info');
    } else if (status === 'ERROR') {
      setProcessingState(false);
      setSubmittingState(false);
      appendLog(`Lỗi xử lý: ${data.message}`, 'error');

      let suggestion = 'Kiểm tra tệp video đầu vào và thiết lập phần cứng trong phần Cài đặt.';
      if (data.message && data.message.includes('chưa được tải về')) {
        suggestion = 'Mô hình AI chưa có trên máy. Hãy vào Cài đặt -> Mô hình AI để tải mô hình về.';
      } else if (data.message && data.message.includes('FFmpeg')) {
        suggestion = 'FFmpeg gặp sự cố khi xử lý video. Hãy kiểm tra codec hoặc chuyển sang CPU trong Cài đặt.';
      }

      showErrorModal({
        title: 'Lỗi trong quá trình xử lý',
        message: data.message,
        suggestion: suggestion,
        details: data.details || data.message
      });
    }
  }

  async function cancelPipeline() {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ action: 'CANCEL' }));
      } catch (e) {}
    }
    const tid = getCurrentTaskId();
    if (tid) {
      try {
        await fetch('/api/pipeline/cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_id: tid })
        });
      } catch (e) {}
    }
    setProcessingState(false);
    setSubmittingState(false);
    updateConnectionStatus('ready');
    updateProgress(0, 'Đã hủy tác vụ.', '', null);
    appendLog('Đã hủy tác vụ theo yêu cầu người dùng.', 'warn');
    showToast('Đã hủy tiến trình thành công.', 'info');
  }

  async function sendPhase2(editedSrt, subStyle) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        action: 'RESUME_WITH_SCRIPT',
        edited_srt: editedSrt,
        sub_style: subStyle
      }));
    } else {
      const res = await fetch('/api/re-render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: getCurrentTaskId(),
          edited_srt: editedSrt,
          sub_style: subStyle
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Lỗi render phụ đề');
      }
      handleWsMessage(data);
    }
  }

  return { connectWebSocket, sendPhase2, cancelPipeline };
}
