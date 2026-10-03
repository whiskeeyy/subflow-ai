import re
import requests
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from openai import OpenAI


def clean_markdown_fences(content: str) -> str:
    """
    Removes optional markdown code fences ```srt ... ``` or ``` ... ```
    if emitted by a language model.
    """
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:srt)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)
    return content.strip()


def translate_single_text_gtx(text: str) -> str:
    """
    Translates a single string from Chinese to Vietnamese using Google Translate (Free GTX endpoint).
    """
    if not text or not text.strip():
        return ""
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": "vi",
        "dt": "t",
        "q": text.strip()
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            translated = "".join([item[0] for item in data[0] if item[0]]).strip()
            return translated if translated else text.strip()
    except Exception:
        pass
    return text.strip()


def translate_srt_free_google(chinese_srt: str, output_srt_path: Optional[str] = None) -> str:
    """
    Free translation engine:
    Parses SRT blocks, translates subtitle texts in parallel,
    and reconstructs the exact original SRT timestamps and sequence numbers.
    100% free, 0 API key required, 100% timestamp preservation.
    """
    if not chinese_srt.strip():
        raise ValueError("Nội dung phụ đề tiếng Trung (SRT) bị trống.")

    pattern = re.compile(
        r"(\d+)\s*\r?\n(\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\r?\n([\s\S]*?)(?=(?:\r?\n\s*\r?\n|\Z))",
        re.MULTILINE
    )

    matches = list(pattern.finditer(chinese_srt.strip()))
    if not matches:
        return chinese_srt

    parsed_blocks = [
        (m.group(1), m.group(2).replace(".", ","), m.group(3).strip())
        for m in matches
    ]

    # Parallel translation for high speed
    with ThreadPoolExecutor(max_workers=5) as executor:
        translated_texts = list(executor.map(translate_single_text_gtx, [b[2] for b in parsed_blocks]))

    result_entries = []
    for (idx, time_range, _), trans_text in zip(parsed_blocks, translated_texts):
        final_text = trans_text if trans_text else "..."
        result_entries.append(f"{idx}\n{time_range}\n{final_text}\n")

    vietnamese_srt = "\n".join(result_entries).strip() + "\n"

    if output_srt_path:
        out_p = Path(output_srt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(vietnamese_srt, encoding="utf-8")

    return vietnamese_srt


def translate_srt_openai(chinese_srt: str, api_key: str, output_srt_path: Optional[str] = None) -> str:
    """
    Translates Chinese SRT using OpenAI GPT-4o-mini if an API key is available.
    """
    if not api_key:
        raise ValueError("OPENAI_API_KEY chưa được thiết lập.")

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "Bạn là chuyên gia dịch thuật và biên tập phụ đề video ngắn (TikTok, Douyin, Reels, Shorts). "
        "Nhiệm vụ của bạn là dịch file phụ đề SRT tiếng Trung sang tiếng Việt giọng đọc tự nhiên, hấp dẫn, chuẩn văn phong lồng tiếng Việt Nam.\n\n"
        "CÁC QUY TẮC BẮT BUỘC:\n"
        "1. GIỮ NGUYÊN 100% CẤU TRÚC SRT: Giữ nguyên số thứ tự câu (1, 2, 3...) và mốc thời gian "
        "   dạng '00:00:01,000 --> 00:00:04,000'. Tuyệt đối không thay đổi hay xóa mốc thời gian.\n"
        "2. VĂN PHONG TỰ NHIÊN: Dịch thoát ý, tự nhiên như lời người Việt đang kể chuyện hoặc lồng tiếng. "
        "   Chuyển ngữ các thành ngữ, tiếng lóng tiếng Trung sang cách nói đời thường của người Việt.\n"
        "3. ĐỊNH DẠNG ĐẦU RA: Chỉ trả về nội dung text SRT thuần túy. KHÔNG bọc trong markdown code block (không dùng ``` hay ```srt). "
        "   KHÔNG thêm bất kỳ lời mở đầu, giải thích hay ghi chú nào."
    )
    user_prompt = f"Hãy dịch file phụ đề SRT tiếng Trung sau đây sang tiếng Việt:\n\n{chinese_srt}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )
    vietnamese_srt = clean_markdown_fences(response.choices[0].message.content or "")

    if output_srt_path:
        out_p = Path(output_srt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(vietnamese_srt, encoding="utf-8")

    return vietnamese_srt


def translate_srt_to_vietnamese(
    chinese_srt: str,
    api_key: Optional[str] = None,
    output_srt_path: Optional[str] = None,
    prefer_openai: bool = False
) -> str:
    """
    Main Translation Dispatcher:
    - Default: Free Google Translate (0 cost, no API keys, preserves 100% of timestamps).
    - If prefer_openai is True and a valid key exists, attempts GPT-4o-mini with automatic fallback.
    """
    if prefer_openai and api_key and api_key.startswith("sk-"):
        try:
            return translate_srt_openai(chinese_srt, api_key, output_srt_path)
        except Exception as e:
            print(f"[TRANSLATE] OpenAI error: {e}. Falling back to Free Google Translate...")

    return translate_srt_free_google(chinese_srt, output_srt_path)
