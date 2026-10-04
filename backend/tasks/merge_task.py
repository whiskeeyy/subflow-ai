import logging
import os
import sys
import shutil
import subprocess
import re
import time
from pathlib import Path
from typing import Optional, Callable

from backend.settings_manager import settings_manager

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


def _parse_time_str(t_str: str) -> float:
    try:
        parts = t_str.strip().split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return 0.0


def _run_ffmpeg_pipeline(
    cmd: list,
    out_path: Path,
    total_duration_sec: Optional[float] = None,
    progress_callback: Optional[Callable[[int, str, str, Optional[float]], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    on_process_started: Optional[Callable[[subprocess.Popen], None]] = None
) -> str:
    """
    Executes FFmpeg with -progress pipe:1, parsing real-time progress (fps, speed, out_time, ETA)
    silently without console windows, and handles cancellation cleanly.
    """
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        **kwargs
    )

    if on_process_started:
        on_process_started(proc)

    detected_duration = total_duration_sec or 0.0
    last_callback_time = 0.0
    error_buffer = []

    current_fps = "0"
    current_speed = "1.0x"
    current_out_time_sec = 0.0

    duration_regex = re.compile(r"Duration:\s*(\d+:\d+:\d+\.?\d*)")

    try:
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            line_str = line.strip()
            error_buffer.append(line_str)
            if len(error_buffer) > 25:
                error_buffer.pop(0)

            if cancel_check and cancel_check():
                try:
                    proc.kill()
                except Exception:
                    pass
                if out_path.exists():
                    try:
                        out_path.unlink()
                    except Exception:
                        pass
                raise RuntimeError("Tác vụ nhúng phụ đề đã bị người dùng hủy bỏ.")

            if detected_duration <= 0:
                d_match = duration_regex.search(line_str)
                if d_match:
                    detected_duration = _parse_time_str(d_match.group(1))

            if "=" in line_str:
                k, _, v = line_str.partition("=")
                k = k.strip()
                v = v.strip()
                if k == "fps":
                    current_fps = v
                elif k == "speed":
                    current_speed = v
                elif k == "out_time":
                    current_out_time_sec = _parse_time_str(v)
                elif k == "progress" and v == "end":
                    if progress_callback:
                        progress_callback(100, current_speed, current_fps, 0.0)

            now = time.time()
            if (now - last_callback_time >= 0.25) and (detected_duration > 0) and (current_out_time_sec > 0):
                last_callback_time = now
                pct = min(99, max(0, int((current_out_time_sec / detected_duration) * 100)))
                eta_sec = None
                try:
                    spd_mult = float(current_speed.replace("x", "").strip())
                    if spd_mult > 0:
                        eta_sec = max(0.0, (detected_duration - current_out_time_sec) / spd_mult)
                except Exception:
                    pass

                if progress_callback:
                    progress_callback(pct, current_speed, current_fps, eta_sec)

        proc.stdout.close()
        proc.wait()

        if cancel_check and cancel_check():
            raise RuntimeError("Tác vụ nhúng phụ đề đã bị người dùng hủy bỏ.")

        if proc.returncode != 0:
            last_err = "\n".join(error_buffer[-8:])
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=last_err)

    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        if cancel_check and cancel_check():
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass
            raise RuntimeError("Tác vụ nhúng phụ đề đã bị người dùng hủy bỏ.") from exc
        raise

    return str(out_path)


def burn_subtitles_to_video(
    video_path: str,
    srt_path: str,
    output_path: str,
    primary_color: Optional[str] = None,
    font_size: Optional[int] = None,
    margin_v: Optional[int] = None,
    font_name: Optional[str] = None,
    play_res_y: int = 1080,
    use_gpu: bool = True,
    total_duration_sec: Optional[float] = None,
    progress_callback: Optional[Callable[[int, str, str, Optional[float]], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    on_process_started: Optional[Callable[[subprocess.Popen], None]] = None
) -> str:
    """
    Burns hard subtitles into video while preserving original audio (-c:a copy).
    Supports GPU acceleration (NVENC), real-time progress callbacks, and instantaneous cancellation.
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

    # 1. Clean & Normalize style configurations (fallback to settings if None)
    settings = settings_manager.get_settings()
    preset = settings.get("subtitle_preset", {})

    chosen_color = primary_color if primary_color is not None else preset.get("color_bgr", "&H0000FFFF&")
    chosen_font_size = font_size if font_size is not None else preset.get("font_size", 54)
    chosen_margin_v = margin_v if margin_v is not None else preset.get("margin_v", 90)
    chosen_font_name = font_name if font_name is not None else preset.get("font_name", "Arial Black")

    color_bgr = hex_rgb_to_ass_bgr(chosen_color)
    safe_play_res_y = int(play_res_y) if play_res_y else 1080
    safe_font_size = max(14, min(140, int(chosen_font_size)))
    safe_margin_v = max(10, min(600, int(chosen_margin_v)))

    # 2. Build ASS force_style string with explicit PlayResY for standard scaling across any aspect ratio/resolution
    force_style_str = (
        f"FontName={chosen_font_name},Bold=1,FontSize={safe_font_size},"
        f"PrimaryColour={color_bgr},Outline=3.5,OutlineColour=&H00000000&,"
        f"BorderStyle=1,Alignment=2,PlayResY={safe_play_res_y},MarginV={safe_margin_v}"
    )

    # 3. Subtitles filter with properly escaped Windows path
    escaped_srt = format_ffmpeg_sub_path(str(s_path))
    sub_filter = f"subtitles=filename='{escaped_srt}':force_style='{force_style_str}'"

    # Base FFmpeg input with nostdin and progress pipe
    base_args = [
        ffmpeg_bin,
        "-nostdin",
        "-progress", "pipe:1",
        "-i", str(v_path),
        "-vf", sub_filter,
    ]

    # Resolve encoder from settings
    resolved_encoder = settings_manager.get_resolved_encoder()
    can_use_gpu = use_gpu and (resolved_encoder == "h264_nvenc")

    # 4. Attempt GPU Acceleration (h264_nvenc) if resolved to nvenc
    if can_use_gpu:
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
            return _run_ffmpeg_pipeline(
                gpu_cmd,
                out_path,
                total_duration_sec=total_duration_sec,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                on_process_started=on_process_started
            )
        except subprocess.CalledProcessError as exc:
            logger.warning(
                f"GPU h264_nvenc không khả dụng hoặc lỗi: {exc.output[-200:] if exc.output else ''}. "
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
        return _run_ffmpeg_pipeline(
            cpu_cmd,
            out_path,
            total_duration_sec=total_duration_sec,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            on_process_started=on_process_started
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg render video thất bại: {exc.output}") from exc
