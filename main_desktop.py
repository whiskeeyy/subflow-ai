"""
SubFlow AI - Standalone Native Desktop Entrypoint.
Runs FastAPI backend inside a background daemon thread with dynamic port binding,
and renders the modern UI inside a native Microsoft Edge WebView2 (Chromium) window via pywebview.
"""
import os
import sys
import time
import socket
import logging
import threading
import webbrowser
import ctypes
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
import webview
from backend.app import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("subflow_desktop")


def is_webview2_available() -> bool:
    """
    Checks if Microsoft Edge WebView2 Runtime is installed on the host machine.
    Inspects 32-bit and 64-bit Windows registry hives and pywebview winforms engine.
    """
    # 1. Registry checks
    try:
        import winreg
        guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"),
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"),
            (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{guid}"),
        ]
        for root, subkey in reg_paths:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "pv")
                    if val and str(val) != "0":
                        logger.info(f"Phát hiện Microsoft Edge WebView2 Runtime (phiên bản: {val})")
                        return True
            except OSError:
                continue
    except Exception as e:
        logger.warning(f"Lỗi kiểm tra WebView2 qua registry: {e}")

    # 2. Pywebview winforms check fallback
    try:
        import webview.platforms.winforms as wf
        if getattr(wf, "is_chromium", False):
            return True
    except Exception:
        pass

    return False


def show_webview2_missing_dialog() -> bool:
    """
    Displays a native Windows MessageBox informing the user that WebView2 Runtime is required.
    Offers a direct action to open the official Microsoft download page.
    """
    msg = (
        "SubFlow AI yêu cầu Microsoft Edge WebView2 Runtime để khởi chạy giao diện Desktop.\n\n"
        "Hệ thống chưa phát hiện WebView2 Runtime trên máy tính của bạn.\n\n"
        "Bạn có muốn mở trình duyệt để tải gói cài đặt chính thức (Evergreen Bootstrapper) từ Microsoft ngay bây giờ không?"
    )
    title = "SubFlow AI - Cần cài đặt WebView2 Runtime"
    MB_YESNO = 0x00000004
    MB_ICONWARNING = 0x00000030
    IDYES = 6

    try:
        res = ctypes.windll.user32.MessageBoxW(0, msg, title, MB_YESNO | MB_ICONWARNING)
        if res == IDYES:
            webbrowser.open("https://go.microsoft.com/fwlink/p/?LinkId=2124703")
            return True
    except Exception as exc:
        logger.error(f"Không thể hiển thị hộp thoại cảnh báo: {exc}")
        print(f"\n[CẢNH BÁO] {msg}\nLink: https://go.microsoft.com/fwlink/p/?LinkId=2124703\n", file=sys.stderr)

    return False


def find_free_port() -> int:
    """
    Finds an unused local port to prevent port collisions with other applications.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 12.0) -> bool:
    """
    Polls the local server until it begins accepting TCP connections.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)
    return False


def main():
    print("=" * 65)
    print("  SubFlow AI Studio - Phiên bản Desktop")
    print("  Đang khởi tạo môi trường và kiểm tra tài nguyên hệ thống...")
    print("=" * 65)

    # 1. WebView2 Runtime Verification
    if not is_webview2_available():
        logger.error("Microsoft Edge WebView2 Runtime không khả dụng.")
        show_webview2_missing_dialog()
        sys.exit(1)

    # 2. Dynamic Port Allocation
    port = find_free_port()
    app_url = f"http://127.0.0.1:{port}"
    logger.info(f"Khởi động máy chủ cục bộ trên cổng động: {port}")

    # 3. Start FastAPI Server in a Background Daemon Thread
    server_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        loop="asyncio"
    )
    server = uvicorn.Server(server_config)
    server_thread = threading.Thread(target=server.run, daemon=True, name="subflow_uvicorn_worker")
    server_thread.start()

    # 4. Wait for Server to be Ready
    if not wait_for_server(port, timeout=12.0):
        logger.error(f"Máy chủ cục bộ không phản hồi trên cổng {port} sau 12 giây.")
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Không thể khởi động dịch vụ máy chủ nội bộ trên cổng {port}.\nVui lòng kiểm tra quyền hệ thống hoặc phần mềm diệt virus.",
            "SubFlow AI - Lỗi khởi động",
            0x00000010  # MB_ICONERROR
        )
        sys.exit(1)

    logger.info(f"Máy chủ đã sẵn sàng tại {app_url}. Đang mở cửa sổ ứng dụng...")

    # 5. Window Icon Resolution
    icon_path = BUNDLE_DIR / "frontend" / "assets" / "logo.ico"
    icon = str(icon_path) if icon_path.exists() else None

    # 6. Create Native Desktop Window
    window = webview.create_window(
        title="SubFlow AI - Studio Phụ Đề Video Ngắn",
        url=app_url,
        width=1420,
        height=920,
        min_size=(1024, 700),
        resizable=True,
        fullscreen=False,
        confirm_close=False,
        background_color="#0d1117"
    )

    # 7. Clean Shutdown Callback
    def on_closed():
        logger.info("Cửa sổ SubFlow AI đã đóng. Đang gửi tín hiệu dừng máy chủ...")
        server.should_exit = True

    window.events.closed += on_closed

    # 8. Start PyWebView GUI Loop (blocks until window is closed)
    try:
        webview.start(gui="edgechromium", icon=icon)
    except Exception as exc:
        logger.error(f"Lỗi hiển thị giao diện pywebview: {exc}", exc_info=True)
    finally:
        logger.info("Đang dọn dẹp và kết thúc tiến trình SubFlow AI...")
        server.should_exit = True
        server_thread.join(timeout=1.5)
        logger.info("SubFlow AI đã tắt hoàn tất.")
        os._exit(0)


if __name__ == "__main__":
    main()
