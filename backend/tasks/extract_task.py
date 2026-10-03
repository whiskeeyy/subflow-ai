import os
import sys
import shutil
import subprocess
from pathlib import Path


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


def extract_audio_from_video(video_path: str, output_audio_path: str) -> str:
    """
    Extracts audio stream from a local video file using FFmpeg:
    ffmpeg -i <video_path> -q:a 0 -map a <output_audio_path> -y
    """
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        raise RuntimeError(
            "Không tìm thấy công cụ FFmpeg trên hệ thống. "
            "Vui lòng cài đặt FFmpeg (VD: winget install Gyan.FFmpeg) và thêm vào biến môi trường PATH."
        )

    v_path = Path(video_path).resolve()
    a_path = Path(output_audio_path).resolve()

    if not v_path.exists():
        raise FileNotFoundError(f"Tệp video không tồn tại: {video_path}")

    a_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-i", str(v_path),
        "-q:a", "0",
        "-map", "a",
        str(a_path),
        "-y"
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Lỗi khi trích xuất âm thanh bằng FFmpeg: {exc.stderr.strip()}"
        ) from exc

    return str(a_path)
