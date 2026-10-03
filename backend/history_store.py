"""
Shared project history storage module.
Keeps a history.json in the outputs directory.
Used by app.py (upload/re-render) and video_pipeline.py (on SUCCESS).
"""
import json
import datetime
from pathlib import Path

from backend.config import OUTPUTS_DIR

HISTORY_FILE = OUTPUTS_DIR / "history.json"


def load_history() -> list:
    items = []
    if HISTORY_FILE.exists():
        try:
            items = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            items = []

    # Auto-discover task folders in OUTPUTS_DIR that might not be recorded
    known_ids = {h.get("task_id") for h in items}
    modified = False

    if OUTPUTS_DIR.exists():
        for task_path in OUTPUTS_DIR.glob("task_*"):
            if task_path.is_dir() and task_path.name not in known_ids:
                has_final = (task_path / "final_video.mp4").exists()
                has_video = (task_path / "video_goc.mp4").exists()
                if has_final or has_video:
                    stat = task_path.stat()
                    dt = datetime.datetime.fromtimestamp(stat.st_mtime)
                    items.append({
                        "task_id": task_path.name,
                        "filename": f"{task_path.name}.mp4",
                        "status": "done" if has_final else "processing",
                        "created_date": dt.date().isoformat(),
                        "time": dt.strftime("%H:%M"),
                        "video_url": f"/outputs/{task_path.name}/video_goc.mp4",
                        "srt_url": f"/outputs/{task_path.name}/sub_viet.srt",
                        "final_video_url": f"/outputs/{task_path.name}/final_video.mp4",
                    })
                    known_ids.add(task_path.name)
                    modified = True

    if modified:
        # Sort by creation time desc
        items.sort(key=lambda x: (x.get("created_date", ""), x.get("time", "")), reverse=True)
        save_history(items[:50])

    return items


def save_history(items: list) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def upsert_history(entry: dict) -> None:
    """Insert or update a history entry keyed by task_id. Keeps last 50."""
    items = load_history()
    idx = next(
        (i for i, h in enumerate(items) if h.get("task_id") == entry["task_id"]), -1
    )
    if idx >= 0:
        items[idx].update(entry)
    else:
        items.insert(0, entry)
    save_history(items[:50])


def mark_task_done(task_id: str) -> None:
    """Mark a task as completed in history."""
    upsert_history({"task_id": task_id, "status": "done"})


def create_task_entry(task_id: str, filename: str) -> None:
    """Create initial 'processing' entry when upload starts."""
    now = datetime.datetime.now()
    upsert_history({
        "task_id": task_id,
        "filename": filename,
        "status": "processing",
        "created_date": now.date().isoformat(),
        "time": now.strftime("%H:%M"),
        "video_url": f"/outputs/{task_id}/video_goc.mp4",
        "srt_url": f"/outputs/{task_id}/sub_viet.srt",
        "final_video_url": f"/outputs/{task_id}/final_video.mp4",
    })
