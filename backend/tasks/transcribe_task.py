import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Callable
from faster_whisper import WhisperModel
from backend.settings_manager import settings_manager
from backend.model_downloader import model_downloader

logger = logging.getLogger("transcribe_task")


class ModelNotFoundError(Exception):
    """Raised when the specified Whisper model has not been downloaded locally."""
    pass


# Cache WhisperModel instance across requests
_cached_model: Optional[WhisperModel] = None
_cached_model_key: Optional[Tuple[str, str, str]] = None


def _resolve_model_source(model_name: str) -> str:
    """Finds local model directory or validates HuggingFace cache."""
    local_path = model_downloader.find_model_path(model_name)
    if local_path:
        return str(local_path)

    # Fallback: check if model exists in HuggingFace cache
    user_profile = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    if user_profile:
        hf_dir = Path(user_profile) / ".cache" / "huggingface" / "hub"
        if hf_dir.exists():
            for item in hf_dir.iterdir():
                if item.is_dir() and f"whisper-{model_name}" in item.name.lower():
                    return model_name

    raise ModelNotFoundError(
        f"Mô hình Whisper '{model_name}' chưa được tải về máy tính. "
        f"Vui lòng vào 'Cài đặt' -> 'Mô hình AI' hoặc Wizard để tải mô hình trước khi tiếp tục."
    )


def get_whisper_model(force_cpu: bool = False) -> WhisperModel:
    """
    Dynamically loads and caches the WhisperModel instance based on current settings.
    Checks local offline model directory first. Raises ModelNotFoundError if not downloaded.
    Reloads only if model size, device, or compute_type has changed.
    Supports force_cpu=True for automatic runtime fallback.
    """
    global _cached_model, _cached_model_key

    settings = settings_manager.get_settings()
    model_name = settings.get("ai", {}).get("whisper_model", "base")
    device = "cpu" if force_cpu else settings_manager.get_resolved_device()
    compute_type = "float16" if device == "cuda" else "int8"

    current_key = (model_name, device, compute_type)

    if _cached_model is None or _cached_model_key != current_key:
        model_source = _resolve_model_source(model_name)
        logger.info(f"Nạp mô hình Whisper: {model_name} (Thiết bị: {device}, Compute: {compute_type})...")

        try:
            _cached_model = WhisperModel(model_source, device=device, compute_type=compute_type)
            _cached_model_key = current_key
            logger.info("Nạp mô hình Whisper thành công.")
        except Exception as e:
            if device == "cuda":
                logger.warning(f"Không thể khởi tạo Whisper trên CUDA ({e}). Tự động fallback về CPU (int8)...")
                _cached_model = WhisperModel(model_source, device="cpu", compute_type="int8")
                _cached_model_key = (model_name, "cpu", "int8")
            else:
                raise e

    return _cached_model


def format_time(seconds: float) -> str:
    """
    Converts raw seconds into strict SRT timestamp format: HH:MM:SS,mmm
    Example: 1.5 -> 00:00:01,500
    Ensures milliseconds are exactly 3 digits separated by a comma (,).
    """
    total_seconds = int(seconds)
    millis = int(round((seconds - total_seconds) * 1000))
    if millis >= 1000:
        total_seconds += 1
        millis -= 1000

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_audio(
    audio_path: str,
    api_key: Optional[str] = None,
    output_srt_path: Optional[str] = None,
    progress_callback: Optional[Callable[[float, float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Tuple[str, float]:
    """
    Transcribes audio locally using faster-whisper and returns a tuple (srt_content, duration_seconds).
    Emits granular real-time progress callbacks and supports instantaneous cancellation.
    Language is loaded dynamically from settings (defaults to 'zh').
    Automatically falls back to CPU (int8) if CUDA runtime error (e.g. missing cuBLAS DLL or OOM) occurs.
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Tệp âm thanh không tồn tại: {audio_path}")

    model = get_whisper_model()
    settings = settings_manager.get_settings()
    lang = settings.get("ai", {}).get("language", "zh")

    def _execute_transcribe(active_model: WhisperModel) -> Tuple[list, float]:
        segments, info = active_model.transcribe(str(path), language=lang)
        total_dur = float(info.duration) if info and info.duration else 0.0

        entries = []
        index = 1

        for segment in segments:
            if cancel_check and cancel_check():
                logger.info("Transcribe cancelled by user.")
                raise RuntimeError("Tác vụ nhận diện giọng nói đã bị người dùng hủy bỏ.")

            text = segment.text.strip()
            if not text:
                continue

            start_time = format_time(segment.start)
            end_time = format_time(segment.end)

            entry = f"{index}\n{start_time} --> {end_time}\n{text}\n"
            entries.append(entry)
            index += 1

            if progress_callback and total_dur > 0:
                progress_callback(segment.end, total_dur, text)

        return entries, total_dur

    try:
        srt_entries, total_duration = _execute_transcribe(model)
    except Exception as e:
        err_msg = str(e).lower()
        if ("cublas" in err_msg or "cuda" in err_msg or "cudnn" in err_msg) and _cached_model_key and _cached_model_key[1] == "cuda":
            logger.warning(f"Lỗi khi thực thi Whisper trên CUDA ({e}). Tự động chuyển đổi sang CPU (int8) để tiếp tục...")
            model = get_whisper_model(force_cpu=True)
            srt_entries, total_duration = _execute_transcribe(model)
        else:
            raise e

    if cancel_check and cancel_check():
        raise RuntimeError("Tác vụ nhận diện giọng nói đã bị người dùng hủy bỏ.")

    srt_content = "\n".join(srt_entries).strip()
    if srt_content:
        srt_content += "\n"

    if output_srt_path:
        out_p = Path(output_srt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(srt_content, encoding="utf-8")

    return srt_content, total_duration
