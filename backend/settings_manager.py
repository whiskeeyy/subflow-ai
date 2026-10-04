import os
import sys
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("settings_manager")

# Base project paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_OUTPUTS_DIR = str(PROJECT_ROOT / "outputs")

# Default Settings Schema
DEFAULT_SETTINGS: Dict[str, Any] = {
    "storage": {
        "output_dir": DEFAULT_OUTPUTS_DIR,
        "auto_cleanup_audio": True,
        "auto_cleanup_source_video": False
    },
    "ai": {
        "whisper_model": "base",
        "device": "auto",
        "language": "zh"
    },
    "hardware": {
        "encoder": "auto",
        "gpu_device_id": 0
    },
    "translation": {
        "engine": "google_gtx",
        "api_key": ""
    },
    "subtitle_preset": {
        "color_bgr": "&H0000FFFF&",
        "font_size": 20,
        "margin_v": 140,
        "font_name": "Arial Black"
    }
}


def get_settings_file_path() -> Path:
    """
    Determines the settings.json path with priority:
    1st Priority: %APPDATA%/SubFlowAI/settings.json (Standard Windows desktop data directory)
    Fallback: Local project root ./settings.json
    """
    appdata = os.environ.get("APPDATA")
    if appdata and sys.platform == "win32":
        try:
            app_dir = Path(appdata) / "SubFlowAI"
            app_dir.mkdir(parents=True, exist_ok=True)
            return app_dir / "settings.json"
        except Exception as e:
            logger.warning(f"Could not initialize APPDATA folder: {e}. Falling back to project root.")

    # Fallback to local project directory
    return PROJECT_ROOT / "settings.json"


def get_models_dir() -> Path:
    """
    Determines the models directory path with priority:
    1st Priority: %APPDATA%/SubFlowAI/models/ (Windows user profile)
    Fallback: Local project directory ./models/
    """
    appdata = os.environ.get("APPDATA")
    if appdata and sys.platform == "win32":
        try:
            models_dir = Path(appdata) / "SubFlowAI" / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            return models_dir
        except Exception as e:
            logger.warning(f"Could not initialize APPDATA models folder: {e}. Falling back to local.")

    local_models = PROJECT_ROOT / "models"
    local_models.mkdir(parents=True, exist_ok=True)
    return local_models


def find_ffmpeg_bin() -> str:
    """Finds ffmpeg binary in bundled package, local ffmpeg_bin, or system PATH."""
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "ffmpeg_bin" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)

    local_bin = PROJECT_ROOT / "ffmpeg_bin" / "ffmpeg.exe"
    if local_bin.exists():
        return str(local_bin)

    p = shutil.which("ffmpeg")
    return p or ""


def diagnose_system() -> Dict[str, Any]:
    """
    Inspects system hardware and environment:
    - NVIDIA GPU detection (name, total VRAM)
    - FFmpeg NVENC encoder support
    - Local / cached Whisper models
    - Resolves 'auto' choices into concrete values
    """
    has_nvidia_gpu = False
    gpu_name = ""
    vram_gb = 0.0

    # 1. NVIDIA GPU Detection via nvidia-smi
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            line = res.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            gpu_name = parts[0]
            if len(parts) > 1:
                vram_mb = float(parts[1])
                vram_gb = round(vram_mb / 1024.0, 1)
            has_nvidia_gpu = True
    except Exception:
        # Fallback to checking PyTorch / CTranslate2 if available
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                has_nvidia_gpu = True
                gpu_name = "NVIDIA CUDA Device"
        except Exception:
            pass

    # 2. FFmpeg NVENC Encoder Detection
    has_nvenc = False
    ffmpeg_exe = find_ffmpeg_bin()
    if ffmpeg_exe:
        try:
            enc_res = subprocess.run(
                [ffmpeg_exe, "-encoders"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "h264_nvenc" in enc_res.stdout:
                has_nvenc = True
        except Exception as e:
            logger.warning(f"Error checking ffmpeg encoders: {e}")

    # 3. Detect Installed Models
    installed_models = set()
    for search_dir in [get_models_dir(), PROJECT_ROOT / "models"]:
        if search_dir.exists():
            for item in search_dir.iterdir():
                if item.is_dir() and (item / "model.bin").exists():
                    name = item.name.lower().replace("whisper-", "")
                    for sz in ["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"]:
                        if sz in name:
                            installed_models.add(sz)

    # Check HuggingFace hub cache
    try:
        user_profile = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
        if user_profile:
            hf_hub = Path(user_profile) / ".cache" / "huggingface" / "hub"
            if hf_hub.exists():
                for item in hf_hub.iterdir():
                    if item.is_dir() and "whisper" in item.name.lower():
                        for sz in ["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"]:
                            if sz in item.name.lower():
                                installed_models.add(sz)
    except Exception as e:
        logger.warning(f"Error checking HF cache: {e}")

    # 4. Resolve automatic selections
    resolved_device = "cuda" if has_nvidia_gpu else "cpu"
    resolved_encoder = "h264_nvenc" if (has_nvenc and has_nvidia_gpu) else "libx264"

    return {
        "has_nvidia_gpu": has_nvidia_gpu,
        "gpu_name": gpu_name,
        "vram_gb": vram_gb,
        "has_nvenc": has_nvenc,
        "resolved_device": resolved_device,
        "resolved_encoder": resolved_encoder,
        "installed_models": sorted(list(installed_models))
    }


class SettingsManager:
    """
    Manages persistent settings with atomic read/write and automatic default merge.
    """
    _instance: Optional["SettingsManager"] = None

    def __init__(self):
        self.file_path = get_settings_file_path()
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    @classmethod
    def get_instance(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = SettingsManager()
        return cls._instance

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merges override dictionary into base dictionary."""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def load_settings(self) -> Dict[str, Any]:
        """Reads settings.json or initializes it with default values."""
        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                loaded = json.loads(content)
                self._settings = self._deep_merge(DEFAULT_SETTINGS, loaded)
                return self._settings
            except Exception as e:
                logger.error(f"Error reading {self.file_path}: {e}. Restoring defaults.")

        # If file doesn't exist or errored, write defaults
        self._settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        self._write_file(self._settings)
        return self._settings

    def _write_file(self, data: Dict[str, Any]):
        """Atomically writes data to settings.json using a temp file."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")
        try:
            temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            temp_file.replace(self.file_path)
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            logger.error(f"Failed to save settings: {e}")
            raise IOError(f"Không thể ghi cấu hình: {e}")

    def save_settings(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validates and updates settings atomically."""
        merged = self._deep_merge(self._settings, new_config)

        # Validate output directory path if present
        if "storage" in merged and "output_dir" in merged["storage"]:
            out_dir = Path(merged["storage"]["output_dir"])
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                # Test write permission
                test_file = out_dir / ".subflow_write_test"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink()
            except Exception as exc:
                raise ValueError(f"Thư mục lưu trữ không hợp lệ hoặc không có quyền ghi: {out_dir} ({exc})")

        self._settings = merged
        self._write_file(self._settings)
        logger.info(f"Settings saved successfully to {self.file_path}")
        return self._settings

    def reset_settings(self) -> Dict[str, Any]:
        """Resets settings to factory defaults."""
        self._settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        self._write_file(self._settings)
        logger.info("Settings reset to defaults.")
        return self._settings

    def get_settings(self) -> Dict[str, Any]:
        """Returns the current in-memory settings."""
        if not self._settings:
            return self.load_settings()
        return self._settings

    def get_output_dir(self) -> Path:
        """Returns verified Path for output_dir from settings."""
        out = self.get_settings().get("storage", {}).get("output_dir", DEFAULT_OUTPUTS_DIR)
        p = Path(out).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_models_dir(self) -> Path:
        """Returns verified Path for offline models directory."""
        return get_models_dir()

    def get_resolved_device(self) -> str:
        """Resolves 'auto' device to 'cuda' or 'cpu'."""
        configured = self.get_settings().get("ai", {}).get("device", "auto")
        if configured == "auto":
            diag = diagnose_system()
            return diag["resolved_device"]
        return configured

    def get_resolved_encoder(self) -> str:
        """Resolves 'auto' encoder to 'h264_nvenc' or 'libx264'."""
        configured = self.get_settings().get("hardware", {}).get("encoder", "auto")
        if configured == "auto":
            diag = diagnose_system()
            return diag["resolved_encoder"]
        return configured


settings_manager = SettingsManager.get_instance()
