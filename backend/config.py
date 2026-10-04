import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def get_bundle_dir() -> Path:
    """
    Returns the root directory of the application bundle.
    In development mode: root project directory.
    In PyInstaller frozen mode (--onedir): directory where sys.executable resides or sys._MEIPASS.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# Base project & bundle paths
PROJECT_ROOT = get_bundle_dir()
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FFMPEG_BIN_DIR = PROJECT_ROOT / "ffmpeg_bin"

# Auto-register bundled ffmpeg_bin into PATH if present
if FFMPEG_BIN_DIR.exists():
    ffmpeg_bin_str = str(FFMPEG_BIN_DIR.resolve())
    current_path = os.environ.get("PATH", "")
    if ffmpeg_bin_str not in current_path:
        os.environ["PATH"] = ffmpeg_bin_str + os.pathsep + current_path

# Load environment variables from .env file
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
WHISPER_MODEL = "whisper-1"
TRANSLATION_MODEL = "gpt-4o-mini"

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Edge-TTS Supported Voices
VOICE_OPTIONS = {
    "vi-VN-NamMinhNeural": "Nam Minh (Nam - Giọng chuẩn, truyền cảm)",
    "vi-VN-HoaiMyNeural": "Hoài My (Nữ - Giọng ngọt ngào, tự nhiên)"
}

RATE_OPTIONS = ["-10%", "+0%", "+10%", "+15%", "+20%", "+25%"]
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "vi-VN-NamMinhNeural")
DEFAULT_RATE = os.getenv("DEFAULT_RATE", "+0%")

# Ensure output directory exists (fallback)
try:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
