import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
WHISPER_MODEL = "whisper-1"
TRANSLATION_MODEL = "gpt-4o-mini"

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Edge-TTS Supported Voices
VOICE_OPTIONS = {
    "vi-VN-NamMinhNeural": "Nam Minh (Nam - Giọng chuẩn, truyền cảm)",
    "vi-VN-HoaiMyNeural": "Hoài My (Nữ - Giọng ngọt ngào, tự nhiên)"
}

RATE_OPTIONS = ["-10%", "+0%", "+10%", "+15%", "+20%", "+25%"]
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "vi-VN-NamMinhNeural")
DEFAULT_RATE = os.getenv("DEFAULT_RATE", "+0%")

# Ensure output directory exists
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
