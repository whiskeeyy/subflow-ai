import re
from pathlib import Path
import edge_tts


def extract_spoken_text_from_srt(srt_content: str) -> str:
    """
    Parses clean spoken text from an SRT subtitle string:
    - Strips numeric sequence indices (e.g. '1', '2')
    - Strips timestamp lines ('00:00:01,000 --> 00:00:04,000')
    - Strips HTML tags (e.g. <i>, <b>, <font>)
    - Joins remaining spoken lines cleanly for TTS synthesis.
    """
    timestamp_pattern = re.compile(
        r"^\d{1,2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{3}"
    )
    sequence_pattern = re.compile(r"^\d+$")

    clean_lines = []
    for line in srt_content.splitlines():
        line = line.strip()
        if not line:
            continue
        if sequence_pattern.match(line):
            continue
        if timestamp_pattern.match(line):
            continue
        # Remove any stray HTML subtitle formatting tags
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            clean_lines.append(line)

    return " ".join(clean_lines)


async def synthesize_speech(
    text: str,
    output_mp3_path: str,
    voice: str = "vi-VN-NamMinhNeural",
    rate: str = "+0%"
) -> str:
    """
    Synthesizes speech from clean text using edge-tts.
    """
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Không có nội dung văn bản để tạo giọng đọc.")

    out_file = Path(output_mp3_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate)
    await communicate.save(str(out_file))

    return str(out_file.resolve())


async def generate_narration_from_srt(
    srt_content: str,
    output_mp3_path: str,
    output_srt_path: str = None,
    voice: str = "vi-VN-NamMinhNeural",
    rate: str = "+0%"
) -> dict:
    """
    Extracts spoken sentences from SRT, saves final sub_viet.srt,
    and synthesizes voice_viet.mp3 via edge-tts.
    """
    if output_srt_path:
        out_srt = Path(output_srt_path)
        out_srt.parent.mkdir(parents=True, exist_ok=True)
        out_srt.write_text(srt_content, encoding="utf-8")

    spoken_text = extract_spoken_text_from_srt(srt_content)
    if not spoken_text:
        raise ValueError("Không thể trích xuất văn bản thoại từ nội dung phụ đề SRT đã chỉnh sửa.")

    audio_file = await synthesize_speech(
        text=spoken_text,
        output_mp3_path=output_mp3_path,
        voice=voice,
        rate=rate
    )

    return {
        "voice_path": audio_file,
        "srt_path": str(Path(output_srt_path).resolve()) if output_srt_path else None,
        "clean_text": spoken_text
    }
