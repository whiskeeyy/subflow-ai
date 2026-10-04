"""
Batch Processing & Task Queue Manager for SubFlow AI.
Processes Phase 1 (transcription + translation) sequentially in the background.
Allows reviewing scripts and batch rendering Phase 2.
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from backend.settings_manager import settings_manager
from backend.workflows.video_pipeline import VideoRepurposePipeline
from backend.tasks.merge_task import burn_subtitles_to_video
from backend.history_store import mark_task_done, create_task_entry

logger = logging.getLogger("batch_manager")


class BatchManager:
    _instance: Optional["BatchManager"] = None

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._render_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "BatchManager":
        if cls._instance is None:
            cls._instance = BatchManager()
        return cls._instance

    def start_worker(self):
        """Starts the background worker task if not running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("Batch background worker started.")

    async def add_task(self, task_id: str, filename: str) -> Dict[str, Any]:
        """Registers a new task and pushes it into the background queue."""
        task_info = {
            "task_id": task_id,
            "filename": filename,
            "status": "pending",
            "percent": 0,
            "message": "Đang xếp hàng chờ xử lý AI...",
            "video_url": f"/outputs/{task_id}/video_goc.mp4",
            "srt_url": f"/outputs/{task_id}/sub_viet.srt",
            "final_video_url": f"/outputs/{task_id}/final_video.mp4",
            "error": None
        }
        self._tasks[task_id] = task_info
        create_task_entry(task_id, filename)
        await self._queue.put(task_id)
        self.start_worker()
        return task_info

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    def update_task_srt(self, task_id: str, srt_content: str) -> bool:
        """Saves edited SRT content for a task in the queue."""
        task_dir = OUTPUTS_DIR / task_id
        srt_file = task_dir / "sub_viet.srt"
        try:
            srt_file.write_text(srt_content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Error saving SRT for {task_id}: {e}")
            return False

    async def _process_queue(self):
        """Continuously pulls tasks from queue and executes audio extraction & translation sequentially."""
        logger.info("Batch Queue processor is running...")
        while True:
            try:
                task_id = await self._queue.get()
                task = self._tasks.get(task_id)
                if not task:
                    self._queue.task_done()
                    continue

                task["status"] = "processing"
                task["percent"] = 10
                task["message"] = "Bắt đầu bóc tách & dịch thuật AI..."

                async def emitter(event: dict):
                    status = event.get("status")
                    if status == "PROGRESS":
                        task["percent"] = event.get("percent", task["percent"])
                        task["message"] = event.get("message", task["message"])
                    elif status == "ACTION_REQUIRED":
                        task["status"] = "waiting_review"
                        task["percent"] = 75
                        task["message"] = "Đã dịch xong. Chờ duyệt kịch bản!"
                    elif status == "ERROR":
                        task["status"] = "error"
                        task["error"] = event.get("message", "Lỗi không xác định")

                try:
                    pipeline = VideoRepurposePipeline(task_id=task_id, emitter=emitter)
                    await pipeline.run_phase_1()
                    task["status"] = "waiting_review"
                    task["percent"] = 75
                    task["message"] = "Đã dịch xong. Chờ duyệt kịch bản!"
                except Exception as exc:
                    logger.error(f"Batch task {task_id} failed during transcription/translation: {exc}", exc_info=True)
                    task["status"] = "error"
                    task["error"] = str(exc)
                    task["message"] = f"Lỗi: {str(exc)}"

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in batch queue worker: {e}", exc_info=True)
                await asyncio.sleep(1)

    def trigger_render_task(self, task_id: str, sub_style: Optional[dict] = None) -> Dict[str, Any]:
        """Kích hoạt nhúng phụ đề cho 1 tác vụ chạy bất đồng bộ (non-blocking)."""
        outputs_dir = settings_manager.get_output_dir()
        task = self._tasks.get(task_id)
        if not task:
            task_dir = outputs_dir / task_id
            if task_dir.exists():
                task = {
                    "task_id": task_id,
                    "filename": task_id,
                    "status": "waiting_review",
                    "percent": 75,
                    "message": "Sẵn sàng duyệt",
                    "video_url": f"/outputs/{task_id}/video_goc.mp4",
                    "srt_url": f"/outputs/{task_id}/sub_viet.srt",
                    "final_video_url": f"/outputs/{task_id}/final_video.mp4",
                    "error": None
                }
                self._tasks[task_id] = task
            else:
                raise ValueError(f"Task {task_id} không tồn tại trong hàng đợi.")

        task["status"] = "rendering"
        task["percent"] = 80
        task["message"] = "Đang chuẩn bị nhúng phụ đề..."
        asyncio.create_task(self._safe_render_task(task_id, sub_style))
        return task

    async def _safe_render_task(self, task_id: str, sub_style: Optional[dict] = None):
        """Thực thi nhúng phụ đề tuần tự qua render_lock để bảo vệ tài nguyên GPU/CPU."""
        async with self._render_lock:
            try:
                await self.render_task(task_id, sub_style)
            except Exception as e:
                logger.error(f"Render failed for {task_id}: {e}", exc_info=True)

    async def render_task(self, task_id: str, sub_style: Optional[dict] = None) -> Dict[str, Any]:
        """Renders hardsubs for a single task."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} không tồn tại trong hàng đợi.")

        outputs_dir = settings_manager.get_output_dir()
        task_dir = outputs_dir / task_id
        video_path = task_dir / "video_goc.mp4"
        srt_path = task_dir / "sub_viet.srt"
        final_video_path = task_dir / "final_video.mp4"

        if not video_path.exists() or not srt_path.exists():
            raise FileNotFoundError("Không tìm thấy file video hoặc srt của task.")

        style = sub_style or {}
        primary_color = style.get("color_bgr", "&H0000FFFF&")
        font_size = int(style.get("font_size", 54))
        margin_v = int(style.get("margin_v", 90))
        play_res_y = int(style.get("play_res_y", 1080))

        task["status"] = "rendering"
        task["percent"] = 85
        task["message"] = "Đang nhúng phụ đề bằng FFmpeg..."

        try:
            await asyncio.to_thread(
                burn_subtitles_to_video,
                video_path=str(video_path),
                srt_path=str(srt_path),
                output_path=str(final_video_path),
                primary_color=primary_color,
                font_size=font_size,
                margin_v=margin_v,
                play_res_y=play_res_y,
                use_gpu=True
            )
            task["status"] = "done"
            task["percent"] = 100
            task["message"] = "Nhúng phụ đề hoàn tất!"
            mark_task_done(task_id)
            return task
        except Exception as exc:
            logger.error(f"Error rendering task {task_id}: {exc}", exc_info=True)
            task["status"] = "error"
            task["error"] = str(exc)
            task["message"] = f"Lỗi render: {str(exc)}"
            raise

    async def render_all_reviewed(self, sub_style: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Renders all tasks currently in 'waiting_review' state."""
        async with self._render_lock:
            tasks_to_render = [
                tid for tid, t in self._tasks.items()
                if t.get("status") == "waiting_review"
            ]
            results = []
            for tid in tasks_to_render:
                try:
                    res = await self.render_task(tid, sub_style)
                    results.append(res)
                except Exception as e:
                    logger.error(f"Batch render failed for {tid}: {e}")
            return results


# Global singleton
batch_manager = BatchManager.get_instance()
