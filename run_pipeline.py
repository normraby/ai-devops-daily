#!/usr/bin/env python3
"""Run the full AI DevOps Daily content pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from script_utils import LOGS_DIR, OUTPUT_DIR, parse_header, script_path

PROJECT_ROOT = Path(__file__).resolve().parent
TRACKER_FILE = PROJECT_ROOT / "tracker.json"
STATUS_FILE = LOGS_DIR / "last_run_status.json"
PIPELINE_LOG = LOGS_DIR / "pipeline_log.txt"
MAX_VIDEO_NUMBER = 20
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(PIPELINE_LOG),
        ],
    )


def load_tracker() -> dict:
    if not TRACKER_FILE.exists():
        return {"last_uploaded": 0, "videos": {}}
    return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))


def save_tracker(tracker: dict) -> None:
    TRACKER_FILE.write_text(json.dumps(tracker, indent=2) + "\n", encoding="utf-8")


def write_run_status(payload: dict) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_step(script_name: str, video_number: int) -> dict | None:
    command = [sys.executable, str(PROJECT_ROOT / script_name), str(video_number)]
    logging.info("Running: %s", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    if result.stdout.strip():
        logging.info(result.stdout.strip())
    if result.stderr.strip():
        logging.warning(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed with exit code {result.returncode}")

    if script_name == "upload_to_youtube.py" and result.stdout.strip():
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return None
    return None


def run_pipeline() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Run AI DevOps Daily pipeline")
    parser.add_argument("--video", type=int, default=None, help="Override video number to process")
    args = parser.parse_args()

    tracker = load_tracker()
    if args.video is not None:
        video_number = args.video
        logging.info("Video number overridden by --video flag: %s", video_number)
    else:
        video_number = int(tracker.get("last_uploaded", 0)) + 1

    logging.info("Starting pipeline for video %s", video_number)

    title = ""
    try:
        title = parse_header(script_path(video_number).read_text(encoding="utf-8")).get("title", "")
    except OSError:
        title = f"AI DevOps Daily #{video_number}"

    prev_status = tracker.get("videos", {}).get(str(video_number), {}).get("status")
    if prev_status == "failed":
        logging.info("Previous attempt failed — cleaning up partial output files for video %s", video_number)
        for ext in ["mp3", "mp4", "jpg"]:
            path = OUTPUT_DIR / f"thumbnail_{video_number}.jpg" if ext == "jpg" else OUTPUT_DIR / f"video_{video_number}.{ext}"
            if path.exists():
                path.unlink()
                logging.info("Deleted partial file: %s", path)

    if video_number > MAX_VIDEO_NUMBER:
        logging.info(
            "All %d videos have been processed (last_uploaded=%s). Stopping.",
            MAX_VIDEO_NUMBER,
            tracker.get("last_uploaded"),
        )
        write_run_status(
            {
                "video_number": video_number,
                "title": title,
                "status": "complete",
                "message": "All videos processed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return 0

    steps = [
        "generate_voiceover.py",
        "generate_video.py",
        "generate_thumbnail.py",
        "upload_to_youtube.py",
    ]

    try:
        upload_result: dict | None = None
        for step in steps:
            upload_result = run_step(step, video_number) or upload_result

        entry = {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "status": "uploaded",
        }
        if upload_result:
            entry["video_id"] = upload_result.get("video_id", "")
            entry["url"] = upload_result.get("url", "")
            if upload_result.get("title"):
                title = upload_result["title"]

        tracker["last_uploaded"] = video_number
        tracker.setdefault("videos", {})[str(video_number)] = entry
        save_tracker(tracker)

        write_run_status(
            {
                "video_number": video_number,
                "title": title,
                "status": "uploaded",
                "video_id": entry.get("video_id", ""),
                "url": entry.get("url", ""),
                "timestamp": entry["processed_at"],
            }
        )
        logging.info("Pipeline completed successfully for video %s", video_number)
        return 0
    except Exception as exc:
        logging.exception("Pipeline failed for video %s: %s", video_number, exc)
        failed_at = datetime.now(timezone.utc).isoformat()
        tracker.setdefault("videos", {})[str(video_number)] = {
            "processed_at": failed_at,
            "status": "failed",
            "error": str(exc),
        }
        save_tracker(tracker)
        write_run_status(
            {
                "video_number": video_number,
                "title": title,
                "status": "failed",
                "error": str(exc),
                "timestamp": failed_at,
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(run_pipeline())
