import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional

from backend.config import OUTPUTS_DIR, OPENAI_API_KEY
from backend.tasks.extract_task import extract_audio_from_video
from backend.tasks.transcribe_task import transcribe_audio
from backend.tasks.translate_task import translate_srt_to_vietnamese
from backend.tasks.merge_task import burn_subtitles_to_video
from backend.history_store import mark_task_done

logger = logging.getLogger("video_pipeline")


class PipelineState:
    INIT = "INIT"
    EXTRACTING = "EXTRACTING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    WAITING_FOR_EDIT = "WAITING_FOR_EDIT"
    BURNING_SUB = "BURNING_SUB"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class VideoRepurposePipeline:
    """
    Subtitles-Only Hardsub Pipeline (with Real-time Interactive Video-Sub Preview):
    - Phase 1: FFmpeg Audio Extraction -> faster-whisper STT -> Google Translate Engine -> Emit ACTION_REQUIRED.
    - Phase 2: Save edited SRT -> Burn Hardsub directly into video (preserving original audio) -> Emit SUCCESS.
    """

    def __init__(
        self,
        task_id: str,
        emitter: Optional[Callable[[dict], Awaitable[None]]] = None
    ):
        raw_id = task_id.replace("task_", "")
        self.task_id = f"task_{raw_id}"
        self.task_dir = OUTPUTS_DIR / self.task_id
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.emitter = emitter
        self.state = PipelineState.INIT

        # Task state context
        self.video_path = self.task_dir / "video_goc.mp4"
        self.audio_path = self.task_dir / "audio_goc.mp3"
        self.chinese_srt = ""
        self.vietnamese_srt = ""
        self.final_srt = ""

    async def emit(self, data: dict):
        if self.emitter:
            await self.emitter(data)

    async def run_phase_1(self) -> str:
        """
        Executes Phase 1:
        Step 1 (20%): Extract audio from local video_goc.mp4 using FFmpeg (asyncio.to_thread).
        Step 2 (50%): Transcribe audio via local faster-whisper to Chinese SRT.
        Step 3 (75%): Translate Chinese SRT to Vietnamese SRT using Free Google Translate engine.
        PAUSE: Emit ACTION_REQUIRED with srt_content & video_url for interactive preview.
        """
        if not self.video_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy tệp video đầu vào: {self.video_path}. Vui lòng tải file lên lại."
            )

        try:
            # Step 1: Extract Audio (20%)
            self.state = PipelineState.EXTRACTING
            await self.emit({
                "status": "PROGRESS",
                "percent": 20,
                "step": "EXTRACT_AUDIO",
                "message": "Đang trích xuất luồng âm thanh gốc từ video bằng FFmpeg..."
            })

            await asyncio.to_thread(
                extract_audio_from_video,
                str(self.video_path),
                str(self.audio_path)
            )

            # Step 2: Transcribe via local faster-whisper (50%)
            self.state = PipelineState.TRANSCRIBING
            await self.emit({
                "status": "PROGRESS",
                "percent": 50,
                "step": "TRANSCRIBE",
                "message": "Đang gọi faster-whisper cục bộ để bóc tách lời thoại tiếng Trung và tạo mốc thời gian SRT..."
            })
            chinese_srt_path = self.task_dir / "sub_chinese.srt"
            self.chinese_srt = await asyncio.to_thread(
                transcribe_audio,
                audio_path=str(self.audio_path),
                api_key=OPENAI_API_KEY,
                output_srt_path=str(chinese_srt_path)
            )

            # Auto-Clean: Remove temporary audio_goc.mp3 to save disk space
            try:
                if self.audio_path.exists():
                    self.audio_path.unlink()
                    logger.info(f"Auto-Clean: Đã xóa file âm thanh tạm {self.audio_path.name}")
            except Exception as e:
                logger.warning(f"Auto-Clean: Không thể xóa {self.audio_path}: {e}")

            # Step 3: Translate to Vietnamese (75%)
            self.state = PipelineState.TRANSLATING
            await self.emit({
                "status": "PROGRESS",
                "percent": 75,
                "step": "TRANSLATE",
                "message": "Đang dịch kịch bản sang tiếng Việt (Bảo toàn 100% mốc thời gian SRT)..."
            })
            viet_srt_path = self.task_dir / "sub_viet_raw.srt"
            self.vietnamese_srt = await asyncio.to_thread(
                translate_srt_to_vietnamese,
                chinese_srt=self.chinese_srt,
                api_key=OPENAI_API_KEY,
                output_srt_path=str(viet_srt_path)
            )
            # Also save default sub_viet.srt so it can be previewed/rendered immediately
            (self.task_dir / "sub_viet.srt").write_text(self.vietnamese_srt, encoding="utf-8")

            # PAUSE: Await Human Review & Live Interactive Preview
            self.state = PipelineState.WAITING_FOR_EDIT
            await self.emit({
                "status": "ACTION_REQUIRED",
                "action": "EDIT_SCRIPT",
                "task_id": self.task_id,
                "srt_content": self.vietnamese_srt,
                "video_url": f"/outputs/{self.task_id}/video_goc.mp4",
                "message": "Kịch bản phụ đề tiếng Việt đã sẵn sàng! Bạn có thể xem trước video và tùy chỉnh phụ đề trực tiếp."
            })

            return self.vietnamese_srt

        except Exception as e:
            self.state = PipelineState.ERROR
            await self.emit({
                "status": "ERROR",
                "message": f"Lỗi ở Phase 1: {str(e)}"
            })
            raise

    async def run_phase_2(self, edited_srt: str, sub_style: Optional[dict] = None) -> dict:
        """
        Executes Phase 2:
        Step 4 (80%): Save confirmed SRT file.
        Step 5 (90%): Burn hard subtitles directly into video preserving original audio via FFmpeg.
        Step 6 (100%): Emit SUCCESS with final_video path.
        """
        try:
            self.state = PipelineState.BURNING_SUB
            self.final_srt = edited_srt

            # Unpack subtitle styling options
            sub_cfg = sub_style or {}
            primary_color = sub_cfg.get("color_bgr", "&H0000FFFF&")
            font_size = int(sub_cfg.get("font_size", 54))
            margin_v = int(sub_cfg.get("margin_v", 90))
            play_res_y = int(sub_cfg.get("play_res_y", 1080))

            final_srt_path = self.task_dir / "sub_viet.srt"
            final_video_path = self.task_dir / "final_video.mp4"

            # Save confirmed edited SRT
            final_srt_path.write_text(self.final_srt, encoding="utf-8")

            # Step 5: Burn hard subtitles directly into video (90%)
            await self.emit({
                "status": "PROGRESS",
                "percent": 90,
                "step": "BURN_SUB",
                "message": "Đang nhúng phụ đề trực tiếp vào video bằng FFmpeg (giữ nguyên âm thanh gốc)..."
            })

            await asyncio.to_thread(
                burn_subtitles_to_video,
                video_path=str(self.video_path),
                srt_path=str(final_srt_path),
                output_path=str(final_video_path),
                primary_color=primary_color,
                font_size=font_size,
                margin_v=margin_v,
                play_res_y=play_res_y,
                use_gpu=True
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
            self.state = PipelineState.ERROR
            await self.emit({
                "status": "ERROR",
                "message": f"Lỗi ở Phase 2: {str(e)}"
            })
            raise
