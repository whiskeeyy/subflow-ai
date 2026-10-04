import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from faster_whisper import WhisperModel
from backend.settings_manager import settings_manager

logger = logging.getLogger("transcribe_task")

# Cache WhisperModel instance across requests
_cached_model: Optional[WhisperModel] = None
_cached_model_key: Optional[Tuple[str, str, str]] = None


def get_whisper_model() -> WhisperModel:
    """
    Dynamically loads and caches the WhisperModel instance based on current settings.
    Reloads only if model size, device, or compute_type has changed.
    """
    global _cached_model, _cached_model_key

    settings = settings_manager.get_settings()
    model_name = settings.get("ai", {}).get("whisper_model", "base")
    device = settings_manager.get_resolved_device()
    compute_type = "float16" if device == "cuda" else "int8"

    current_key = (model_name, device, compute_type)

    if _cached_model is None or _cached_model_key != current_key:
        logger.info(f"Khởi tạo mô hình Whisper: {model_name} (Thiết bị: {device}, Compute: {compute_type})...")
        try:
            _cached_model = WhisperModel(model_name, device=device, compute_type=compute_type)
            _cached_model_key = current_key
            logger.info("Nạp mô hình Whisper thành công.")
        except Exception as e:
            if device == "cuda":
                logger.warning(f"Không thể khởi tạo Whisper trên CUDA ({e}). Tự động fallback về CPU (int8)...")
                _cached_model = WhisperModel(model_name, device="cpu", compute_type="int8")
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
    output_srt_path: Optional[str] = None
) -> str:
    """
    Transcribes audio locally using faster-whisper and returns a valid SRT string.
    Language is loaded dynamically from settings (defaults to 'zh').
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Tệp âm thanh không tồn tại: {audio_path}")

    model = get_whisper_model()
    settings = settings_manager.get_settings()
    lang = settings.get("ai", {}).get("language", "zh")

    # Transcribe speech with configured language
    segments, info = model.transcribe(str(path), language=lang)

    srt_entries = []
    index = 1

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue

        start_time = format_time(segment.start)
        end_time = format_time(segment.end)

        entry = f"{index}\n{start_time} --> {end_time}\n{text}\n"
        srt_entries.append(entry)
        index += 1

    srt_content = "\n".join(srt_entries).strip()
    if srt_content:
        srt_content += "\n"

    if output_srt_path:
        out_p = Path(output_srt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(srt_content, encoding="utf-8")

    return srt_content
