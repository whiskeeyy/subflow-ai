# FastAPI entrypoint - Upload & Two-Phase Pipeline
import os
import sys
import uuid
import json
import logging
import subprocess
import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import asyncio
from backend.config import (
    FRONTEND_DIR,
    OPENAI_API_KEY,
    VOICE_OPTIONS,
    RATE_OPTIONS,
    DEFAULT_VOICE,
    DEFAULT_RATE
)
from backend.settings_manager import settings_manager, diagnose_system
from backend.workflows.video_pipeline import VideoRepurposePipeline
from backend.tasks.merge_task import burn_subtitles_to_video
from backend.batch_manager import batch_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backend.app")

app = FastAPI(title="SubFlow AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount outputs directory so browser can stream preview audio/video
app.mount("/outputs", StaticFiles(directory=str(settings_manager.get_output_dir())), name="outputs")


@app.get("/api/config")
async def get_config():
    """
    Returns app configuration, voice options, and checks whether OPENAI_API_KEY is configured.
    """
    return {
        "voices": VOICE_OPTIONS,
        "rates": RATE_OPTIONS,
        "default_voice": DEFAULT_VOICE,
        "default_rate": DEFAULT_RATE,
        "openai_configured": bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("your_openai")),
    }


from backend.history_store import load_history, upsert_history, create_task_entry, mark_task_done


@app.get("/api/history")
async def get_history():
    """Returns list of processed projects for the history drawer."""
    items = load_history()
    now = datetime.date.today()

    def friendly_date(iso_str: str) -> str:
        try:
            d = datetime.date.fromisoformat(iso_str)
            if d == now:
                return "Hôm nay"
            elif d == now - datetime.timedelta(days=1):
                return "Hôm qua"
            else:
                return d.strftime("%d/%m/%Y")
        except Exception:
            return iso_str or "Không rõ"

    for item in items:
        item["date"] = friendly_date(item.get("created_date", ""))

    return items


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Receives local video upload, generates unique task_id,
    and stores video as outputs/task_<task_id>/video_goc.mp4.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tệp tải lên không hợp lệ.")

    # Generate a clean short unique task ID
    short_uuid = uuid.uuid4().hex[:8]
    task_id = f"task_{short_uuid}"
    outputs_dir = settings_manager.get_output_dir()
    task_dir = outputs_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    video_dest = task_dir / "video_goc.mp4"

    try:
        # Stream file to disk in 1MB chunks
        with open(video_dest, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as exc:
        logger.error(f"Lỗi khi lưu tệp video tải lên: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Không thể lưu video: {str(exc)}")
    finally:
        await file.close()

    logger.info(f"Video uploaded successfully. Task ID: {task_id}, Path: {video_dest}")

    # Log to project history
    now = datetime.datetime.now()
    create_task_entry(task_id=task_id, filename=file.filename)

    return {
        "task_id": task_id,
        "video_path": str(video_dest.resolve()),
        "filename": file.filename,
    }


# ---------------------------------------------------------------------------
# Batch Processing Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/batch/upload")
async def upload_batch_videos(files: List[UploadFile] = File(...)):
    """
    Receives multiple uploaded videos, creates a task directory for each,
    and automatically registers & enqueues them in the background task queue.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Không có tệp nào được tải lên.")

    outputs_dir = settings_manager.get_output_dir()
    results = []
    for file in files:
        if not file.filename:
            continue

        short_uuid = uuid.uuid4().hex[:8]
        task_id = f"task_{short_uuid}"
        task_dir = outputs_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        video_dest = task_dir / "video_goc.mp4"

        try:
            with open(video_dest, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    buffer.write(chunk)
            
            task_info = await batch_manager.add_task(task_id=task_id, filename=file.filename)
            results.append(task_info)
            logger.info(f"Batch task enqueued: {task_id} ({file.filename})")
        except Exception as exc:
            logger.error(f"Error saving batch file {file.filename}: {exc}")
        finally:
            await file.close()

    return {
        "status": "success",
        "enqueued_count": len(results),
        "tasks": results
    }


@app.get("/api/batch/status")
async def get_batch_status():
    """Returns the live status of all tasks in the batch queue."""
    return batch_manager.get_all_tasks()


@app.get("/api/batch/task/{task_id}")
async def get_batch_task_details(task_id: str):
    """Returns task info and current SRT content for review/editing."""
    task = batch_manager.get_task(task_id)
    outputs_dir = settings_manager.get_output_dir()
    task_dir = outputs_dir / task_id
    srt_file = task_dir / "sub_viet.srt"
    srt_content = ""
    if srt_file.exists():
        srt_content = srt_file.read_text(encoding="utf-8")
    elif (task_dir / "sub_viet_raw.srt").exists():
        srt_content = (task_dir / "sub_viet_raw.srt").read_text(encoding="utf-8")

    return {
        "task": task,
        "srt_content": srt_content,
        "video_url": f"/outputs/{task_id}/video_goc.mp4",
        "final_video_url": f"/outputs/{task_id}/final_video.mp4" if (task_dir / "final_video.mp4").exists() else None
    }


@app.post("/api/batch/task/{task_id}/save-srt")
async def save_batch_task_srt(task_id: str, payload: dict):
    """Saves updated SRT content for a specific batch task."""
    srt_content = payload.get("srt_content", "")
    ok = batch_manager.update_task_srt(task_id, srt_content)
    if not ok:
        raise HTTPException(status_code=500, detail="Không thể lưu file phụ đề.")
    return {"status": "success", "message": "Đã lưu phụ đề thành công."}


@app.post("/api/batch/render-task")
async def render_single_batch_task(payload: dict):
    """Kích hoạt nhúng phụ đề cho 1 tác vụ (non-blocking)."""
    task_id = payload.get("task_id")
    sub_style = payload.get("sub_style", {})
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id không được để trống.")
    try:
        task = batch_manager.trigger_render_task(task_id, sub_style)
        return {"status": "success", "task": task, "message": "Đã bắt đầu nhúng phụ đề vào video."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch/render-all")
async def render_all_batch_tasks(payload: dict):
    """Renders all tasks currently in waiting_review state."""
    sub_style = payload.get("sub_style", {})
    results = await batch_manager.render_all_reviewed(sub_style)
    return {"status": "success", "rendered_count": len(results), "tasks": results}


# ---------------------------------------------------------------------------
# Settings & Hardware Diagnostics Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/settings")
async def get_settings_endpoint():
    """
    Returns current configuration combined with hardware and system diagnostics.
    """
    settings = settings_manager.get_settings()
    diagnostics = await asyncio.to_thread(diagnose_system)
    return {
        "settings": settings,
        "diagnostics": diagnostics
    }


@app.post("/api/settings")
async def update_settings_endpoint(payload: dict):
    """
    Accepts partial or complete settings.
    Validates output directory path and write permissions.
    Writes to settings.json atomically.
    """
    try:
        updated = settings_manager.save_settings(payload)
        # Remount /outputs if directory changed
        new_output_dir = settings_manager.get_output_dir()
        app.mount("/outputs", StaticFiles(directory=str(new_output_dir)), name="outputs")
        return {
            "status": "success",
            "message": "Đã lưu cài đặt thành công.",
            "settings": updated
        }
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/settings/browse-folder")
async def browse_folder_endpoint():
    """
    Opens native Windows folder picker without external GUI dependencies:
    powershell -NoProfile -Command "(New-Object -ComObject Shell.Application).BrowseForFolder(0, 'Chọn thư mục lưu trữ video thành phẩm', 0, 0).Self.Path"
    Executes in a thread with a 60s timeout so the server doesn't hang.
    """
    if sys.platform != "win32":
        return {"path": None, "message": "Chức năng chọn thư mục chỉ hỗ trợ trên hệ điều hành Windows."}

    cmd = '(New-Object -ComObject Shell.Application).BrowseForFolder(0, "Chọn thư mục lưu trữ video thành phẩm", 0, 0).Self.Path'

    def run_picker() -> Optional[str]:
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=60
            )
            out = res.stdout.strip()
            return out if out else None
        except subprocess.TimeoutExpired:
            logger.warning("Folder picker timed out (60s).")
            return None
        except Exception as err:
            logger.error(f"Error running folder picker: {err}")
            return None

    selected_path = await asyncio.to_thread(run_picker)
    return {"path": selected_path}


@app.post("/api/settings/reset")
async def reset_settings_endpoint():
    """
    Resets settings.json to factory defaults and returns the refreshed configuration.
    """
    try:
        defaults = settings_manager.reset_settings()
        return {
            "status": "success",
            "message": "Đã khôi phục cài đặt gốc.",
            "settings": defaults
        }
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/open-folder")
async def open_folder(path: str = Query(..., description="Target directory path to open")):
    """
    Opens the output folder in native file explorer (Windows Explorer, macOS Finder, Linux).
    Includes path traversal validation.
    """
    target = Path(path).resolve()
    base_outputs = settings_manager.get_output_dir().resolve()

    if not str(target).startswith(str(base_outputs)) or not target.exists():
        raise HTTPException(status_code=400, detail="Đường dẫn không hợp lệ hoặc không tồn tại.")

    try:
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=True)
        else:
            subprocess.run(["xdg-open", str(target)], check=True)
        return {"status": "success", "message": f"Đã mở thư mục: {str(target)}"}
    except Exception as e:
        logger.error(f"Không thể mở thư mục {target}: {e}")
        raise HTTPException(status_code=500, detail=f"Không thể mở thư mục: {str(e)}")


@app.post("/api/re-render")
async def re_render_subtitles(payload: dict):
    """
    Re-burns subtitles with modified text and styling without re-running Phase 1.
    Useful for quick iterations or fallback if WebSocket was closed.
    Payload: { "task_id": str, "edited_srt": str, "sub_style": dict }
    """
    task_id = payload.get("task_id", "").strip()
    edited_srt = payload.get("edited_srt", "").strip()
    sub_style = payload.get("sub_style", {})

    if not task_id or not edited_srt:
        raise HTTPException(status_code=400, detail="task_id và edited_srt không được để trống.")

    outputs_dir = settings_manager.get_output_dir()
    task_dir = outputs_dir / task_id
    video_path = task_dir / "video_goc.mp4"
    final_srt_path = task_dir / "sub_viet.srt"
    final_video_path = task_dir / "final_video.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video gốc của tác vụ.")

    # Save updated SRT
    final_srt_path.write_text(edited_srt, encoding="utf-8")

    # Unpack styling with settings fallback
    preset = settings_manager.get_settings().get("subtitle_preset", {})
    primary_color = sub_style.get("color_bgr") or preset.get("color_bgr", "&H0000FFFF&")
    font_size = int(sub_style.get("font_size") or preset.get("font_size", 54))
    margin_v = int(sub_style.get("margin_v") or preset.get("margin_v", 90))
    font_name = sub_style.get("font_name") or preset.get("font_name", "Arial Black")
    play_res_y = int(sub_style.get("play_res_y", 1080))

    try:
        await asyncio.to_thread(
            burn_subtitles_to_video,
            video_path=str(video_path),
            srt_path=str(final_srt_path),
            output_path=str(final_video_path),
            primary_color=primary_color,
            font_size=font_size,
            margin_v=margin_v,
            font_name=font_name,
            play_res_y=play_res_y,
            use_gpu=True
        )
    except Exception as exc:
        logger.error(f"Lỗi khi re-render phụ đề: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi khi render phụ đề: {str(exc)}")

    try:
        mark_task_done(task_id)
    except Exception as e:
        logger.warning(f"History: Không thể cập nhật trạng thái done: {e}")

    return {
        "status": "SUCCESS",
        "task_id": task_id,
        "video_url": f"/outputs/{task_id}/final_video.mp4",
        "output_dir": str(task_dir.resolve()),
        "message": "Cập nhật và nhúng lại phụ đề vào video thành công!"
    }


@app.websocket("/ws/process")
async def websocket_process_endpoint(websocket: WebSocket):
    """
    Two-Phase Human-in-the-loop WebSocket handler for local uploaded files:
    1. Client sends { "task_id": str, "voice": str, "rate": str }
    2. Server runs Phase 1 (FFmpeg Audio Extraction -> Whisper STT -> GPT-4o-mini Translation)
       and emits ACTION_REQUIRED with srt_content.
    3. Client sends { "action": "RESUME_WITH_SCRIPT", "edited_srt": str }
    4. Server runs Phase 2 (Edge-TTS Speech Synthesis -> Output Bundle) and emits SUCCESS.
    """
    await websocket.accept()
    logger.info("WebSocket connection established.")

    async def ws_emitter(data: dict):
        try:
            await websocket.send_text(json.dumps(data, ensure_ascii=False))
        except Exception as err:
            logger.warning(f"Error sending message over WebSocket: {err}")

    try:
        # Phase 1: Wait for initial message with task_id
        init_raw = await websocket.receive_text()
        init_data = json.loads(init_raw)

        task_id = init_data.get("task_id", "").strip()

        if not task_id:
            await ws_emitter({"status": "ERROR", "message": "task_id không hợp lệ hoặc chưa tải video lên."})
            await websocket.close()
            return

        pipeline = VideoRepurposePipeline(task_id=task_id, emitter=ws_emitter)

        # Run Phase 1
        await pipeline.run_phase_1()

        # Phase 2: Await user review/script confirmation (allows re-rendering)
        while True:
            client_msg_raw = await websocket.receive_text()
            client_msg = json.loads(client_msg_raw)

            action = client_msg.get("action")
            if action == "RESUME_WITH_SCRIPT":
                edited_srt = client_msg.get("edited_srt", "")
                sub_style = client_msg.get("sub_style", {})
                await pipeline.run_phase_2(edited_srt=edited_srt, sub_style=sub_style)
                # Keep loop alive so user can review and re-render if needed
            elif action == "CANCEL":
                await ws_emitter({"status": "CANCELLED", "message": "Đã hủy tác vụ theo yêu cầu người dùng."})
                break
            else:
                await ws_emitter({"status": "WARNING", "message": f"Hành động không xác định: {action}"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.error(f"WebSocket execution error: {exc}", exc_info=True)
        try:
            await ws_emitter({"status": "ERROR", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# Serve index.html directly at root URL
@app.get("/")
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse(status_code=404, content={"message": "Frontend index.html not found."})
    return FileResponse(index_file)

# Mount remaining static frontend assets
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
