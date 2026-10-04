import re
import time
import logging
import requests
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
from openai import OpenAI
from backend.settings_manager import settings_manager

logger = logging.getLogger("translate_task")


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


def has_cjk(text: str) -> bool:
    """Checks if a string contains Chinese/Japanese/Korean characters."""
    return any('\u4e00' <= char <= '\u9fff' for char in text)


def translate_single_mymemory(text: str) -> str:
    """Fallback translator using MyMemory API via deep_translator."""
    if not text or not text.strip():
        return ""
    try:
        from deep_translator import MyMemoryTranslator
        res = MyMemoryTranslator(source="zh-CN", target="vi-VN").translate(text.strip())
        if res and not has_cjk(res):
            return res.strip()
    except Exception as exc:
        logger.debug(f"MyMemory fallback error: {exc}")
    return text.strip()


def translate_single_google(text: str) -> str:
    """
    Translates a single string with multi-engine fallback:
    1. clients5 dict-chrome-ex
    2. Google Translate GTX
    3. MyMemory Translator
    """
    if not text or not text.strip():
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://translate.google.com/"
    }

    # Tier 1: clients5 dict-chrome-ex
    try:
        r = requests.get(
            "https://clients5.google.com/translate_a/t",
            params={"client": "dict-chrome-ex", "sl": "auto", "tl": "vi", "q": text.strip()},
            headers=headers,
            timeout=6
        )
        if r.status_code == 200:
            data = r.json()
            first = data[0]
            res_text = first[0] if isinstance(first, list) else first
            if res_text and not has_cjk(res_text):
                return res_text.strip()
    except Exception:
        pass

    # Tier 2: Google GTX single endpoint
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "auto", "tl": "vi", "dt": "t", "q": text.strip()}
        r = requests.get(url, params=params, headers=headers, timeout=6)
        if r.status_code == 200:
            data = r.json()
            translated = "".join([item[0] for item in data[0] if item[0]]).strip()
            if translated and not has_cjk(translated):
                return translated
    except Exception:
        pass

    # Tier 3: MyMemory
    res_mm = translate_single_mymemory(text)
    if res_mm and not has_cjk(res_mm):
        return res_mm

    return text.strip()


def translate_srt_free_google(
    chinese_srt: str,
    output_srt_path: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> str:
    """
    High-Speed Resilient Free Translation Engine:
    - Groups subtitle cues into indexed bracketed batches ([#i] text).
    - Preserves 100% of line order and prevents sentence-merging or rate limits.
    - Emits granular real-time progress callbacks and supports instantaneous cancellation.
    - Automatic fallback for missing or untranslated cues using secondary engines.
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

    total_blocks = len(parsed_blocks)
    translated_map: Dict[int, str] = {}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://translate.google.com/"
    }
    tag_pattern = re.compile(r"\[(\d+)\]\s*(.*?)(?=\s*\[\d+\]|\Z)", re.DOTALL)

    chunk_size = 25
    completed = 0

    for i in range(0, total_blocks, chunk_size):
        if cancel_check and cancel_check():
            raise RuntimeError("Tác vụ dịch thuật đã bị người dùng hủy bỏ.")

        chunk_items = [(idx, parsed_blocks[idx][2]) for idx in range(i, min(i + chunk_size, total_blocks))]
        tagged_text = "\n".join([f"[{idx}] {txt}" for idx, txt in chunk_items])

        # Step 1: Batch translation via clients5 dict-chrome-ex
        try:
            r = requests.get(
                "https://clients5.google.com/translate_a/t",
                params={"client": "dict-chrome-ex", "sl": "auto", "tl": "vi", "q": tagged_text},
                headers=headers,
                timeout=12
            )
            if r.status_code == 200:
                data = r.json()
                first = data[0]
                res_text = first[0] if isinstance(first, list) else first
                found = tag_pattern.findall(res_text)
                for k_str, val in found:
                    try:
                        k_int = int(k_str)
                        v_clean = val.strip()
                        if v_clean:
                            translated_map[k_int] = v_clean
                    except ValueError:
                        pass
            else:
                logger.warning(f"Batch translation returned status {r.status_code}. Using fallback for this chunk.")
        except Exception as exc:
            logger.warning(f"Batch request error for chunk {i}: {exc}")

        # Step 2: Validate each item in chunk; fallback if missing or still contains Chinese
        for idx, orig_text in chunk_items:
            if cancel_check and cancel_check():
                raise RuntimeError("Tác vụ dịch thuật đã bị người dùng hủy bỏ.")

            curr_val = translated_map.get(idx, "")
            if not curr_val or has_cjk(curr_val):
                fallback_val = translate_single_google(orig_text)
                translated_map[idx] = fallback_val

            completed += 1
            if progress_callback:
                progress_callback(completed, total_blocks)

        # Brief pause between chunks to respect API hygiene
        time.sleep(0.08)

    if cancel_check and cancel_check():
        raise RuntimeError("Tác vụ dịch thuật đã bị người dùng hủy bỏ.")

    # Step 3: Reconstruct SRT with 100% timestamp and sequence preservation
    result_entries = []
    cjk_remained = 0

    for idx_num, (seq, time_range, orig_text) in enumerate(parsed_blocks):
        trans_text = translated_map.get(idx_num, orig_text).strip()
        if not trans_text:
            trans_text = "..."
        if has_cjk(trans_text):
            cjk_remained += 1
        result_entries.append(f"{seq}\n{time_range}\n{trans_text}\n")

    if cjk_remained > 0:
        logger.warning(f"Hoàn tất dịch nhưng còn {cjk_remained}/{total_blocks} câu chưa chuyển ngữ được.")

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
    prefer_openai: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> str:
    """
    Main Translation Dispatcher:
    - Reads configured translation engine from settings_manager.
    - Default: High-speed resilient Free Google & MyMemory Engine (0 cost, no API keys, preserves 100% of timestamps).
    - If configured to 'openai' and a valid key exists, attempts GPT-4o-mini with automatic fallback.
    - Emits granular real-time progress callbacks and supports instantaneous cancellation.
    """
    settings = settings_manager.get_settings()
    configured_engine = settings.get("translation", {}).get("engine", "google_gtx")
    configured_key = api_key or settings.get("translation", {}).get("api_key", "")

    if (prefer_openai or configured_engine == "openai") and configured_key and configured_key.startswith("sk-"):
        try:
            return translate_srt_openai(chinese_srt, configured_key, output_srt_path)
        except Exception as e:
            logger.warning(f"OpenAI error: {e}. Tự động chuyển đổi sang Free Engine...")

    return translate_srt_free_google(
        chinese_srt,
        output_srt_path,
        progress_callback=progress_callback,
        cancel_check=cancel_check
    )
