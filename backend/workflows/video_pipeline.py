import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional

from backend.config import OPENAI_API_KEY
from backend.settings_manager import settings_manager
from backend.tasks.extract_task import extract_audio_from_video
from backend.tasks.transcribe_task import transcribe_audio
from backend.tasks.translate_task import translate_srt_to_vietnamese
from backend.tasks.merge_task import burn_subtitles_to_video
from backend.history_store import mark_task_done

logger = logging.getLogger("video_pipeline")


def format_time_simple(seconds: float) -> str:
    """Formats seconds into MM:SS format for readable real-time metrics."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


class PipelineState:
    INIT = "INIT"
    EXTRACTING = "EXTRACTING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    WAITING_FOR_EDIT = "WAITING_FOR_EDIT"
    BURNING_SUB = "BURNING_SUB"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class VideoRepurposePipeline:
    """
    Subtitles-Only Hardsub Pipeline (with Real-time Interactive Video-Sub Preview):
    - Audio Extraction -> faster-whisper STT -> Google Translate Engine -> Emit ACTION_REQUIRED.
    - Save edited SRT -> Burn Hardsub directly into video (preserving original audio) -> Emit SUCCESS.
    - Full cancellation support (instantly terminates subprocesses & AI loops).
    - Granular, real-time progress stream (timestamps, speed, fps, ETA, live sentence preview).
    """

    def __init__(
        self,
        task_id: str,
        emitter: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        raw_id = task_id.replace("task_", "")
        self.task_id = f"task_{raw_id}"
        self.output_dir = settings_manager.get_output_dir()
        self.task_dir = self.output_dir / self.task_id
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.emitter = emitter
        self.state = PipelineState.INIT

        # Task state context
        self.video_path = self.task_dir / "video_goc.mp4"
        self.audio_path = self.task_dir / "audio_goc.mp3"
        self.chinese_srt = ""
        self.vietnamese_srt = ""
        self.final_srt = ""

        # Runtime control & telemetry
        self._cancelled = False
        self._active_proc = None
        self.duration_seconds = 0.0

    async def emit(self, data: dict):
        if self.emitter:
            try:
                await self.emitter(data)
            except Exception as err:
                logger.warning(f"Error emitting websocket message: {err}")

    def cancel(self):
        """Signals cancellation and immediately terminates any active external subprocesses."""
        logger.info(f"Cancellation requested for task: {self.task_id}")
        self._cancelled = True
        self.state = PipelineState.CANCELLED
        if self._active_proc:
            try:
                self._active_proc.kill()
                logger.info(f"Killed active subprocess for {self.task_id}")
            except Exception as e:
                logger.warning(f"Error killing subprocess: {e}")

    async def run_phase_1(self) -> str:
        """
        Executes Phase 1 with live granular telemetry:
        Step 1 (0% -> 15%): Extract audio from local video_goc.mp4 using FFmpeg.
        Step 2 (15% -> 60%): Transcribe audio via local faster-whisper with real-time segment streaming.
        Step 3 (60% -> 79%): Translate Chinese SRT to Vietnamese SRT with live sentence counter.
        PAUSE (80%): Emit ACTION_REQUIRED with srt_content & video_url for interactive preview.
        """
        if not self.video_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy tệp video đầu vào: {self.video_path}. Vui lòng tải file lên lại."
            )

        loop = asyncio.get_running_loop()

        try:
            # Step 1: Extract Audio (0% -> 15%)
            if self._cancelled:
                raise RuntimeError("Tác vụ đã bị người dùng hủy bỏ.")

            self.state = PipelineState.EXTRACTING
            await self.emit({
                "status": "PROGRESS",
                "percent": 5,
                "step": "EXTRACT_AUDIO",
                "message": "[FFmpeg] Đang trích xuất luồng âm thanh gốc từ video..."
            })

            await asyncio.to_thread(
                extract_audio_from_video,
                str(self.video_path),
                str(self.audio_path),
                cancel_check=lambda: self._cancelled,
                on_process_started=lambda proc: setattr(self, "_active_proc", proc)
            )

            # Step 2: Transcribe via local faster-whisper (15% -> 60%)
            if self._cancelled:
                raise RuntimeError("Tác vụ đã bị người dùng hủy bỏ.")

            self.state = PipelineState.TRANSCRIBING
            await self.emit({
                "status": "PROGRESS",
                "percent": 15,
                "step": "TRANSCRIBE",
                "message": "[Whisper AI] Đang khởi động mô hình AI bóc tách giọng nói...",
                "live_text": "Đang phân tích phổ âm thanh..."
            })

            chinese_srt_path = self.task_dir / "sub_chinese.srt"

            def on_whisper_progress(curr_sec: float, total_sec: float, live_text: str):
                self.duration_seconds = total_sec
                # Scale smoothly from 15% to 59%
                ratio = min(1.0, max(0.0, curr_sec / total_sec)) if total_sec > 0 else 0.0
                pct = 15 + int(ratio * 44)
                time_str = f"{format_time_simple(curr_sec)} / {format_time_simple(total_sec)}"
                item_pct = int(ratio * 100)

                asyncio.run_coroutine_threadsafe(
                    self.emit({
                        "status": "PROGRESS",
                        "percent": pct,
                        "step": "TRANSCRIBE",
                        "message": f"[Whisper AI] Đang nhận diện: {time_str} ({item_pct}%)",
                        "live_text": live_text,
                        "metrics": {
                            "time": time_str,
                            "current_sec": round(curr_sec, 1),
                            "total_sec": round(total_sec, 1),
                            "ratio_percent": item_pct
                        }
                    }),
                    loop
                )

            srt_res, detected_duration = await asyncio.to_thread(
                transcribe_audio,
                audio_path=str(self.audio_path),
                api_key=OPENAI_API_KEY,
                output_srt_path=str(chinese_srt_path),
                progress_callback=on_whisper_progress,
                cancel_check=lambda: self._cancelled
            )
            self.chinese_srt = srt_res
            if detected_duration > 0:
                self.duration_seconds = detected_duration

            # Auto-Clean: Remove temporary audio_goc.mp3 based on settings
            if settings_manager.get_settings().get("storage", {}).get("auto_cleanup_audio", True):
                try:
                    if self.audio_path.exists():
                        self.audio_path.unlink()
                        logger.info(f"Auto-Clean: Đã xóa file âm thanh tạm {self.audio_path.name}")
                except Exception as e:
                    logger.warning(f"Auto-Clean: Không thể xóa {self.audio_path}: {e}")

            # Step 3: Translate to Vietnamese (60% -> 79%)
            if self._cancelled:
                raise RuntimeError("Tác vụ đã bị người dùng hủy bỏ.")

            self.state = PipelineState.TRANSLATING
            await self.emit({
                "status": "PROGRESS",
                "percent": 60,
                "step": "TRANSLATE",
                "message": "[Dịch thuật AI] Bắt đầu dịch phụ đề sang tiếng Việt chuẩn văn phong...",
                "live_text": ""
            })

            def on_translate_progress(completed: int, total: int):
                ratio = min(1.0, max(0.0, completed / total)) if total > 0 else 0.0
                pct = 60 + int(ratio * 19)
                item_pct = int(ratio * 100)

                asyncio.run_coroutine_threadsafe(
                    self.emit({
                        "status": "PROGRESS",
                        "percent": pct,
                        "step": "TRANSLATE",
                        "message": f"[Dịch thuật AI] Đang dịch câu {completed}/{total} ({item_pct}%)...",
                        "metrics": {
                            "completed_cues": completed,
                            "total_cues": total,
                            "ratio_percent": item_pct
                        }
                    }),
                    loop
                )

            viet_srt_path = self.task_dir / "sub_viet_raw.srt"
            self.vietnamese_srt = await asyncio.to_thread(
                translate_srt_to_vietnamese,
                chinese_srt=self.chinese_srt,
                api_key=OPENAI_API_KEY,
                output_srt_path=str(viet_srt_path),
                progress_callback=on_translate_progress,
                cancel_check=lambda: self._cancelled
            )
            # Also save default sub_viet.srt so it can be previewed/rendered immediately
            (self.task_dir / "sub_viet.srt").write_text(self.vietnamese_srt, encoding="utf-8")

            # PAUSE: Await Human Review & Live Interactive Preview (80%)
            self.state = PipelineState.WAITING_FOR_EDIT
            await self.emit({
                "status": "ACTION_REQUIRED",
                "action": "EDIT_SCRIPT",
                "task_id": self.task_id,
                "srt_content": self.vietnamese_srt,
                "video_url": f"/outputs/{self.task_id}/video_goc.mp4",
                "duration": self.duration_seconds,
                "message": "Kịch bản phụ đề tiếng Việt đã sẵn sàng! Bạn có thể xem trước video và tùy chỉnh phụ đề trực tiếp."
            })

            return self.vietnamese_srt

        except Exception as e:
            if self._cancelled:
                self.state = PipelineState.CANCELLED
                await self.emit({
                    "status": "CANCELLED",
                    "message": "Đã hủy tiến trình theo yêu cầu của người dùng."
                })
                return ""

            self.state = PipelineState.ERROR
            await self.emit({
                "status": "ERROR",
                "message": f"Lỗi bóc tách & dịch thuật: {str(e)}"
            })
            raise

    async def run_phase_2(self, edited_srt: str, sub_style: Optional[dict] = None) -> dict:
        """
        Executes Phase 2 with live FFmpeg progress telemetry:
        Step 4 (80%): Save confirmed SRT file.
        Step 5 (80% -> 99%): Burn hard subtitles directly into video preserving original audio via FFmpeg.
        Step 6 (100%): Emit SUCCESS with final_video path.
        """
        loop = asyncio.get_running_loop()

        try:
            if self._cancelled:
                raise RuntimeError("Tác vụ đã bị người dùng hủy bỏ.")

            self.state = PipelineState.BURNING_SUB
            self.final_srt = edited_srt

            # Unpack subtitle styling options with settings fallback
            preset = settings_manager.get_settings().get("subtitle_preset", {})
            sub_cfg = sub_style or {}
            primary_color = sub_cfg.get("color_bgr") or preset.get("color_bgr", "&H0000FFFF&")
            font_size = int(sub_cfg.get("font_size") or preset.get("font_size", 54))
            margin_v = int(sub_cfg.get("margin_v") or preset.get("margin_v", 90))
            font_name = sub_cfg.get("font_name") or preset.get("font_name", "Arial Black")
            play_res_y = int(sub_cfg.get("play_res_y", 1080))

            final_srt_path = self.task_dir / "sub_viet.srt"
            final_video_path = self.task_dir / "final_video.mp4"

            # Save confirmed edited SRT
            final_srt_path.write_text(self.final_srt, encoding="utf-8")

            # Step 5: Burn hard subtitles directly into video (80% -> 99%)
            await self.emit({
                "status": "PROGRESS",
                "percent": 80,
                "step": "BURN_SUB",
                "message": "[FFmpeg] Khởi tạo bộ mã hóa video..."
            })

            def on_ffmpeg_progress(render_pct: int, speed: str, fps: str, eta_sec: Optional[float]):
                # Scale from 80% to 99%
                merge_pct = 80 + int((render_pct / 100.0) * 19)
                eta_str = f" • Còn lại ~{int(eta_sec)}s" if (eta_sec is not None and eta_sec > 0) else ""

                asyncio.run_coroutine_threadsafe(
                    self.emit({
                        "status": "PROGRESS",
                        "percent": min(99, merge_pct),
                        "step": "BURN_SUB",
                        "message": f"[FFmpeg] Đang nhúng phụ đề: {render_pct}% ({fps} FPS • Tốc độ {speed}){eta_str}",
                        "metrics": {
                            "render_percent": render_pct,
                            "speed": speed,
                            "fps": fps,
                            "eta_seconds": eta_sec
                        }
                    }),
                    loop
                )

            await asyncio.to_thread(
                burn_subtitles_to_video,
                video_path=str(self.video_path),
                srt_path=str(final_srt_path),
                output_path=str(final_video_path),
                primary_color=primary_color,
                font_size=font_size,
                margin_v=margin_v,
                font_name=font_name,
                play_res_y=play_res_y,
                use_gpu=True,
                total_duration_sec=self.duration_seconds,
                progress_callback=on_ffmpeg_progress,
                cancel_check=lambda: self._cancelled,
                on_process_started=lambda proc: setattr(self, "_active_proc", proc)
            )

            # Step 6: Completed (100%)
            self.state = PipelineState.SUCCESS
            output_dir_abs = str(self.task_dir.resolve())

            success_payload = {
                "status": "SUCCESS",
                "task_id": self.task_id,
                "output_dir": output_dir_abs,
                "files": {
                    "video_goc": str(self.video_path.resolve()),
                    "sub_viet": str(final_srt_path.resolve()),
                    "final_video": str(final_video_path.resolve())
                },
                "relative_paths": {
                    "final_video": f"/outputs/{self.task_id}/final_video.mp4",
                    "video": f"/outputs/{self.task_id}/video_goc.mp4",
                    "sub_viet": f"/outputs/{self.task_id}/sub_viet.srt"
                },
                "video_url": f"/outputs/{self.task_id}/final_video.mp4",
                "message": "Nhúng phụ đề vào video hoàn tất thành công! Đã giữ nguyên 100% âm thanh gốc."
            }

            # Mark project done in history
            try:
                mark_task_done(self.task_id)
            except Exception as e:
                logger.warning(f"History: Không thể cập nhật trạng thái done: {e}")

            await self.emit(success_payload)
            return success_payload

        except Exception as e:
            if self._cancelled:
                self.state = PipelineState.CANCELLED
                await self.emit({
                    "status": "CANCELLED",
                    "message": "Đã hủy tiến trình theo yêu cầu của người dùng."
                })
                return {}

            self.state = PipelineState.ERROR
            await self.emit({
                "status": "ERROR",
                "message": f"Lỗi nhúng phụ đề: {str(e)}"
            })
            raise
