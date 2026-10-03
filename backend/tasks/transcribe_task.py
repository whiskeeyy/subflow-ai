import os
from pathlib import Path
from typing import Optional
from faster_whisper import WhisperModel

# Initialize the model globally (loads once into memory when server starts)
# Using "base", device="cpu", compute_type="int8" for fast local CPU inference
MODEL_SIZE = os.getenv("WHISPER_LOCAL_MODEL", "base")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def format_time(seconds: float) -> str:
    """
    Converts raw seconds into the strict SRT timestamp format: HH:MM:SS,mmm
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
    Language is enforced to Chinese ('zh').
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Tệp âm thanh không tồn tại: {audio_path}")

    # Enforce Chinese speech recognition
    segments, info = model.transcribe(str(path), language="zh")

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
