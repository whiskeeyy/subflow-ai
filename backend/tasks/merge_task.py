import logging
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("merge_task")


def find_ffmpeg() -> str:
    """
    Finds ffmpeg executable from PyInstaller bundle, PATH, or common WinGet installation directories.
    """
    # 1. Check PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "ffmpeg_bin" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)

    # 2. Check local project ffmpeg_bin folder
    local_bin = Path(__file__).resolve().parent.parent.parent / "ffmpeg_bin" / "ffmpeg.exe"
    if local_bin.exists():
        return str(local_bin)

    # 3. Check PATH
    p = shutil.which("ffmpeg")
    if p:
        return p

    # 4. Check WinGet Packages
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkg = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkg.exists():
            matches = list(winget_pkg.glob("**/ffmpeg.exe"))
            if matches:
                return str(matches[0])
    return ""


def format_ffmpeg_sub_path(path: str) -> str:
    """
    Normalizes Windows paths for FFmpeg filter arguments (especially the subtitles filter).
    Replaces backslashes with forward slashes and escapes drive letter colon (e.g., C: -> C\\: in memory).
    """
    abs_path = os.path.abspath(path).replace("\\", "/")
    if len(abs_path) > 1 and abs_path[1] == ":":
        abs_path = abs_path[0] + "\\:" + abs_path[2:]
    return abs_path


def hex_rgb_to_ass_bgr(hex_color: str) -> str:
    """
    Converts CSS hex color (#RRGGBB) to ASS/FFmpeg BGR color format (&H00BBGGRR&).
    Default: #FFFF00 (Yellow) -> &H0000FFFF&
    """
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) == 6:
        r, g, b = cleaned[0:2], cleaned[2:4], cleaned[4:6]
        return f"&H00{b.upper()}{g.upper()}{r.upper()}&"
    elif cleaned.startswith("&H") and cleaned.endswith("&"):
        return cleaned
    return "&H0000FFFF&"


def burn_subtitles_to_video(
    video_path: str,
    srt_path: str,
    output_path: str,
    primary_color: str = "&H0000FFFF&",
    font_size: int = 54,
    margin_v: int = 90,
    play_res_y: int = 1080,
    use_gpu: bool = True
) -> str:
    """
    Burns hard subtitles into video while preserving original audio (-c:a copy).
    1. Clean color hex format for ASS force_style.
    2. Build force_style: FontName=Arial,Bold=1,FontSize=...,PrimaryColour=...,Outline=3.5,OutlineColour=&H00000000&,BorderStyle=1,Alignment=2,PlayResY=1080,MarginV=...
    3. Subtitles filter: subtitles=filename='{escaped_srt}':force_style='{force_style_str}'
    4. FFmpeg cmd: -i video_path -vf sub_filter -c:v h264_nvenc/libx264 -preset veryfast -c:a copy output_path -y
    5. Fallback gracefully to CPU libx264 if NVENC fails.
    """
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        raise RuntimeError("Không tìm thấy công cụ FFmpeg trên hệ thống. Vui lòng kiểm tra biến môi trường PATH.")

    v_path = Path(video_path).resolve()
    s_path = Path(srt_path).resolve()
    out_path = Path(output_path).resolve()

    if not v_path.exists():
        raise FileNotFoundError(f"Tệp video gốc không tồn tại: {video_path}")
    if not s_path.exists():
        raise FileNotFoundError(f"Tệp phụ đề SRT không tồn tại: {srt_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Clean & Normalize style configurations
    color_bgr = hex_rgb_to_ass_bgr(primary_color)
    safe_play_res_y = int(play_res_y) if play_res_y else 1080
    safe_font_size = max(14, min(140, int(font_size)))
    safe_margin_v = max(10, min(600, int(margin_v)))

    # 2. Build ASS force_style string with explicit PlayResY for standard scaling across any aspect ratio/resolution
    force_style_str = (
        f"FontName=Arial,Bold=1,FontSize={safe_font_size},"
        f"PrimaryColour={color_bgr},Outline=3.5,OutlineColour=&H00000000&,"
        f"BorderStyle=1,Alignment=2,PlayResY={safe_play_res_y},MarginV={safe_margin_v}"
    )

    # 3. Subtitles filter with properly escaped Windows path
    escaped_srt = format_ffmpeg_sub_path(str(s_path))
    sub_filter = f"subtitles=filename='{escaped_srt}':force_style='{force_style_str}'"

    # Base FFmpeg input
    base_args = [
        ffmpeg_bin,
        "-i", str(v_path),
        "-vf", sub_filter,
    ]

    # 4. Attempt GPU Acceleration (h264_nvenc)
    if use_gpu:
        gpu_cmd = base_args + [
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-cq", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(out_path),
            "-y"
        ]
        try:
            logger.info("Đang nhúng phụ đề vào video bằng GPU (h264_nvenc)...")
            subprocess.run(
                gpu_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            logger.info(f"Nhúng phụ đề thành công bằng GPU: {out_path}")
            return str(out_path)
        except subprocess.CalledProcessError as exc:
            logger.warning(
                f"GPU h264_nvenc không khả dụng hoặc lỗi: {exc.stderr[-200:] if exc.stderr else ''}. "
                "Tự động chuyển sang CPU encoder (libx264)..."
            )

    # 5. CPU Encoding Fallback (libx264, preset veryfast, lossless audio copy)
    cpu_cmd = base_args + [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out_path),
        "-y"
    ]

    try:
        logger.info("Đang nhúng phụ đề vào video bằng CPU (libx264, preset veryfast)...")
        subprocess.run(
            cpu_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        logger.info(f"Nhúng phụ đề hoàn tất bằng CPU: {out_path}")
        return str(out_path)
    except subprocess.CalledProcessError as exc:
        err_lines = [l.strip() for l in exc.stderr.splitlines() if l.strip()]
        last_error = "\n".join(err_lines[-5:]) if err_lines else exc.stderr[:200]
        logger.error(f"Lỗi khi burn phụ đề bằng FFmpeg: {last_error}")
        raise RuntimeError(f"FFmpeg render video thất bại: {last_error}") from exc
