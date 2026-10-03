"""
SubFlow AI - Desktop Application Entrypoint.
Used for packaging SubFlow AI into a standalone Windows executable (.exe).
Automatically configures bundled FFmpeg, starts Uvicorn server, and opens the default browser.
"""
import os
import sys
import time
import socket
import logging
import threading
import webbrowser
from pathlib import Path

# When packaged by PyInstaller, sys._MEIPASS is the temp extracted directory
if hasattr(sys, "_MEIPASS"):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent

# Ensure project root is in sys.path
sys.path.insert(0, str(BUNDLE_DIR))

# Ensure bundled ffmpeg is in PATH
ffmpeg_dir = BUNDLE_DIR / "ffmpeg_bin"
if ffmpeg_dir.exists():
    os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")

import uvicorn
from backend.config import HOST, PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("subflow_desktop")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def find_available_port(start_port: int = 8000) -> int:
    port = start_port
    while is_port_in_use(port) and port < 8100:
        port += 1
    return port


def open_browser_after_start(url: str, delay: float = 1.5):
    def _worker():
        time.sleep(delay)
        logger.info(f"Opening browser at: {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Could not open browser automatically: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def main():
    target_port = PORT
    if is_port_in_use(target_port):
        # If default port is in use, find another one
        target_port = find_available_port(target_port)

    url = f"http://127.0.0.1:{target_port}"
    print("=" * 60)
    print("  SubFlow AI Studio - Desktop Application")
    print(f"  Giao dien dang mo tai: {url}")
    print("  Vui long giu cua so nay mo trong suot qua trinh su dung.")
    print("=" * 60)

    open_browser_after_start(url, delay=1.2)

    # Import FastAPI app
    from backend.app import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=target_port,
        log_level="info",
        access_log=False
    )


if __name__ == "__main__":
    main()
