"""
Model Downloader Engine for SubFlow AI.
Downloads official Faster-Whisper (CTranslate2) models directly from HuggingFace / HF-Mirror,
with real-time progress tracking (speed, ETA, percentage), resumable chunk streaming,
and atomic directory verification.
"""
import os
import sys
import time
import shutil
import logging
import threading
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.settings_manager import settings_manager, PROJECT_ROOT

logger = logging.getLogger("model_downloader")

# Registry of supported Faster-Whisper models
SUPPORTED_MODELS: Dict[str, Dict[str, Any]] = {
    "tiny": {
        "id": "tiny",
        "name": "Tiny (Siêu nhẹ, ~75 MB)",
        "repo_id": "Systran/faster-whisper-tiny",
        "size_mb": 78.2,
        "vram_req": "1 GB VRAM / CPU",
        "desc": "Tốc độ nhanh nhất, tối ưu máy cấu hình thấp hoặc CPU thông thường."
    },
    "base": {
        "id": "base",
        "name": "Base (Khuyên dùng, ~145 MB)",
        "repo_id": "Systran/faster-whisper-base",
        "size_mb": 147.9,
        "vram_req": "1.5 GB VRAM / CPU",
        "desc": "Cân bằng tối ưu giữa tốc độ & độ chính xác, khuyên dùng cho video ngắn."
    },
    "small": {
        "id": "small",
        "name": "Small (Chuẩn xác, ~480 MB)",
        "repo_id": "Systran/faster-whisper-small",
        "size_mb": 486.2,
        "vram_req": "2.5 GB VRAM / CPU",
        "desc": "Độ chính xác cao hơn, nhận diện tốt âm thanh có nhạc nền hoặc nói nhanh."
    },
    "medium": {
        "id": "medium",
        "name": "Medium (Chuyên sâu, ~1.5 GB)",
        "repo_id": "Systran/faster-whisper-medium",
        "size_mb": 1530.6,
        "vram_req": "4 GB+ VRAM (NVIDIA CUDA)",
        "desc": "Độ chính xác rất cao, khuyên dùng khi có card đồ họa NVIDIA (CUDA)."
    }
}

# Essential files required by faster-whisper (CTranslate2)
ESSENTIAL_FILES = [
    "config.json",
    "tokenizer.json",
    "vocabulary.txt",
    "model.bin"
]

PRIMARY_HOST = "https://huggingface.co"
MIRROR_HOST = "https://hf-mirror.com"


class ModelDownloader:
    """
    Singleton engine managing model downloads and offline model lifecycle.
    """
    _instance: Optional["ModelDownloader"] = None

    def __init__(self):
        self._lock = threading.Lock()
        self._active_thread: Optional[threading.Thread] = None
        self._cancel_requested = False

        self._state: Dict[str, Any] = {
            "model_id": None,
            "status": "IDLE",  # IDLE, DOWNLOADING, COMPLETED, FAILED
            "percent": 0.0,
            "downloaded_mb": 0.0,
            "total_mb": 0.0,
            "speed_mbps": 0.0,
            "eta_seconds": None,
            "error": None
        }

    @classmethod
    def get_instance(cls) -> "ModelDownloader":
        if cls._instance is None:
            cls._instance = ModelDownloader()
        return cls._instance

    def get_progress(self) -> Dict[str, Any]:
        """Returns snapshot of current download state."""
        with self._lock:
            return dict(self._state)

    def find_model_path(self, model_id: str) -> Optional[Path]:
        """
        Locates the directory of an installed model on disk.
        Searches APPDATA models directory first, then local PROJECT_ROOT/models.
        """
        search_dirs = [
            settings_manager.get_models_dir(),
            PROJECT_ROOT / "models"
        ]
        folder_names = [f"whisper-{model_id}", model_id]

        for base_dir in search_dirs:
            if not base_dir.exists():
                continue
            for folder_name in folder_names:
                candidate = base_dir / folder_name
                if candidate.is_dir() and (candidate / "model.bin").exists():
                    return candidate
        return None

    def is_model_installed(self, model_id: str) -> bool:
        """Checks if all required model files are present locally."""
        p = self.find_model_path(model_id)
        if not p:
            return False
        return (p / "model.bin").exists() and (p / "config.json").exists()

    def get_all_models(self) -> List[Dict[str, Any]]:
        """
        Returns the catalog of all supported models with installation status,
        active default flag, and file paths.
        """
        settings = settings_manager.get_settings()
        current_default = settings.get("ai", {}).get("whisper_model", "base")

        result = []
        for mid, meta in SUPPORTED_MODELS.items():
            model_path = self.find_model_path(mid)
            installed = (model_path is not None)
            result.append({
                "id": mid,
                "name": meta["name"],
                "desc": meta["desc"],
                "size_mb": meta["size_mb"],
                "vram_req": meta["vram_req"],
                "installed": installed,
                "path": str(model_path) if model_path else None,
                "is_default": (mid == current_default)
            })
        return result

    def start_download(self, model_id: str) -> Dict[str, Any]:
        """
        Starts downloading a model in a background daemon thread.
        """
        if model_id not in SUPPORTED_MODELS:
            raise ValueError(f"Mô hình không hợp lệ: {model_id}. Các mô hình hỗ trợ: {list(SUPPORTED_MODELS.keys())}")

        with self._lock:
            if self._state["status"] == "DOWNLOADING":
                if self._state["model_id"] == model_id:
                    return {"status": "already_downloading", "model_id": model_id}
                raise RuntimeError(f"Một mô hình khác ({self._state['model_id']}) đang được tải xuống.")

            self._cancel_requested = False
            self._state = {
                "model_id": model_id,
                "status": "DOWNLOADING",
                "percent": 0.0,
                "downloaded_mb": 0.0,
                "total_mb": SUPPORTED_MODELS[model_id]["size_mb"],
                "speed_mbps": 0.0,
                "eta_seconds": None,
                "error": None
            }

        self._active_thread = threading.Thread(
            target=self._download_worker,
            args=(model_id,),
            daemon=True,
            name=f"model_dl_{model_id}"
        )
        self._active_thread.start()
        return {"status": "started", "model_id": model_id}

    def _download_worker(self, model_id: str):
        """Worker executing file downloads with fallback mirrors and chunk streaming."""
        meta = SUPPORTED_MODELS[model_id]
        repo_id = meta["repo_id"]
        models_dir = settings_manager.get_models_dir()
        models_dir.mkdir(parents=True, exist_ok=True)

        target_dir = models_dir / f"whisper-{model_id}"
        temp_dir = models_dir / f"whisper-{model_id}.downloading"
        temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Bắt đầu tải mô hình '{model_id}' ({repo_id}) vào {temp_dir}...")

        try:
            # 1. Fetch file sizes to calculate true total bytes
            file_sizes: Dict[str, int] = {}
            total_bytes = 0

            for fname in ESSENTIAL_FILES:
                size = self._probe_file_size(repo_id, fname)
                file_sizes[fname] = size
                total_bytes += size

            if total_bytes == 0:
                total_bytes = int(meta["size_mb"] * 1024 * 1024)

            with self._lock:
                self._state["total_mb"] = round(total_bytes / (1024 * 1024), 1)

            # 2. Download each essential file
            downloaded_bytes = 0
            last_time = time.time()
            bytes_since_last_calc = 0

            for fname in ESSENTIAL_FILES:
                if self._cancel_requested:
                    raise InterruptedError("Tải mô hình bị hủy bởi người dùng.")

                dest_file = temp_dir / fname
                expected_size = file_sizes.get(fname, 0)

                # Check if file was already fully downloaded previously
                if dest_file.exists() and expected_size > 0 and dest_file.stat().st_size == expected_size:
                    downloaded_bytes += expected_size
                    continue

                # Stream file
                downloaded_bytes = self._download_single_file(
                    repo_id=repo_id,
                    filename=fname,
                    dest_file=dest_file,
                    expected_size=expected_size,
                    overall_downloaded=downloaded_bytes,
                    total_bytes=total_bytes
                )

            # 3. Verification
            for fname in ESSENTIAL_FILES:
                dest = temp_dir / fname
                if not dest.exists() or dest.stat().st_size == 0:
                    raise IOError(f"Tệp tải về không hợp lệ hoặc rỗng: {fname}")

            # 4. Atomic directory rename
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)

            temp_dir.replace(target_dir)
            logger.info(f"Tải và xác thực mô hình '{model_id}' thành công tại: {target_dir}")

            with self._lock:
                self._state["status"] = "COMPLETED"
                self._state["percent"] = 100.0
                self._state["downloaded_mb"] = self._state["total_mb"]
                self._state["speed_mbps"] = 0.0
                self._state["eta_seconds"] = 0

        except Exception as exc:
            logger.error(f"Lỗi khi tải mô hình '{model_id}': {exc}", exc_info=True)
            with self._lock:
                self._state["status"] = "FAILED"
                self._state["error"] = str(exc)

    def _probe_file_size(self, repo_id: str, filename: str) -> int:
        """Queries Content-Length for a file across primary and mirror hosts."""
        for host in [PRIMARY_HOST, MIRROR_HOST]:
            url = f"{host}/{repo_id}/resolve/main/{filename}"
            try:
                resp = requests.head(url, allow_redirects=True, timeout=8)
                if resp.status_code == 200:
                    cl = resp.headers.get("content-length")
                    if cl and cl.isdigit():
                        return int(cl)
            except Exception:
                continue
        return 0

    def _download_single_file(
        self,
        repo_id: str,
        filename: str,
        dest_file: Path,
        expected_size: int,
        overall_downloaded: int,
        total_bytes: int
    ) -> int:
        """Downloads a single file in 128KB chunks with automatic mirror retry and Range resume."""
        hosts = [PRIMARY_HOST, MIRROR_HOST]
        chunk_size = 128 * 1024
        existing_size = dest_file.stat().st_size if dest_file.exists() else 0

        last_calc_time = time.time()
        bytes_in_window = 0

        for host_idx, host in enumerate(hosts):
            url = f"{host}/{repo_id}/resolve/main/{filename}"
            headers = {}
            mode = "wb"

            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"
                mode = "ab"

            try:
                resp = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=12)
                if resp.status_code not in (200, 206):
                    # If Range wasn't accepted, restart file from byte 0
                    if resp.status_code == 416 or (existing_size > 0 and resp.status_code == 200):
                        existing_size = 0
                        headers = {}
                        mode = "wb"
                        resp = requests.get(url, stream=True, allow_redirects=True, timeout=12)

                resp.raise_for_status()

                with open(dest_file, mode) as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self._cancel_requested:
                            raise InterruptedError("Đã nhận yêu cầu hủy tải.")

                        if not chunk:
                            continue

                        f.write(chunk)
                        chunk_len = len(chunk)
                        overall_downloaded += chunk_len
                        bytes_in_window += chunk_len

                        now = time.time()
                        dt = now - last_calc_time
                        if dt >= 0.3:
                            speed_mbps = (bytes_in_window / dt) / (1024 * 1024)
                            percent = min(99.9, round((overall_downloaded / max(1, total_bytes)) * 100, 1))
                            remaining_bytes = max(0, total_bytes - overall_downloaded)
                            speed_bytes_sec = (bytes_in_window / dt)
                            eta = int(remaining_bytes / speed_bytes_sec) if speed_bytes_sec > 0 else 0

                            with self._lock:
                                self._state["percent"] = percent
                                self._state["downloaded_mb"] = round(overall_downloaded / (1024 * 1024), 1)
                                self._state["speed_mbps"] = round(speed_mbps, 2)
                                self._state["eta_seconds"] = eta

                            last_calc_time = now
                            bytes_in_window = 0

                return overall_downloaded

            except Exception as e:
                logger.warning(f"Lỗi tải {filename} từ {host} ({e}). Đang thử nguồn kế tiếp...")
                if host_idx == len(hosts) - 1:
                    raise IOError(f"Không thể tải tệp {filename} từ mọi nguồn: {e}")

        return overall_downloaded

    def delete_model(self, model_id: str, force: bool = False) -> bool:
        """
        Safely removes a downloaded model folder from disk.
        Prevents deletion if the model is currently configured as default unless force is True.
        """
        settings = settings_manager.get_settings()
        current_default = settings.get("ai", {}).get("whisper_model", "base")
        if model_id == current_default and not force:
            raise ValueError(f"Không thể xóa mô hình '{model_id}' vì đang được chọn làm mặc định. Vui lòng chuyển sang mô hình khác trước.")

        model_path = self.find_model_path(model_id)
        if not model_path or not model_path.exists():
            raise FileNotFoundError(f"Mô hình '{model_id}' chưa được tải hoặc không tồn tại.")

        shutil.rmtree(model_path)
        logger.info(f"Đã xóa mô hình '{model_id}' khỏi đĩa: {model_path}")
        return True


model_downloader = ModelDownloader.get_instance()
