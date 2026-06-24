#!/usr/bin/env python3
"""Regenerate and re-upload a video, replacing a zero-view YouTube upload."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.errors import HttpError

from script_utils import OUTPUT_DIR
from upload_to_youtube import get_authenticated_service, upload_to_youtube

PROJECT_ROOT = Path(__file__).resolve().parent
TRACKER_FILE = PROJECT_ROOT / "tracker.json"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stderr)])


def load_tracker() -> dict:
    return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))


def save_tracker(tracker: dict) -> None:
    TRACKER_FILE.write_text(json.dumps(tracker, indent=2) + "\n", encoding="utf-8")


def run_step(script: str, video_number: int) -> None:
    cmd = [sys.executable, str(PROJECT_ROOT / script), str(video_number)]
    logging.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def delete_youtube_video(video_id: str) -> bool:
    youtube = get_authenticated_service()
    try:
        youtube.videos().delete(id=video_id).execute()
        logging.info("Deleted old YouTube video %s", video_id)
        return True
    except HttpError as exc:
        logging.warning("Could not delete %s via API (%s). Remove manually in YouTube Studio.", video_id, exc)
        return False


def regenerate_and_reupload(video_number: int, skip_voiceover: bool = False) -> dict:
    tracker = load_tracker()
    entry = tracker.get("videos", {}).get(str(video_number), {})
    old_video_id = entry.get("video_id", "")

    mp3 = OUTPUT_DIR / f"video_{video_number}.mp3"
    if not skip_voiceover or not mp3.exists():
        run_step("generate_voiceover.py", video_number)

    run_step("generate_video.py", video_number)
    run_step("generate_thumbnail.py", video_number)
    result = upload_to_youtube(video_number)

    if old_video_id and old_video_id != result["video_id"]:
        delete_youtube_video(old_video_id)

    now = datetime.now(timezone.utc).isoformat()
    tracker.setdefault("videos", {})[str(video_number)] = {
        "processed_at": now,
        "status": "uploaded",
        "video_id": result["video_id"],
        "url": result["url"],
        "regenerated_at": now,
        "replaced_video_id": old_video_id or None,
    }
    if int(tracker.get("last_uploaded", 0)) < video_number:
        tracker["last_uploaded"] = video_number
    save_tracker(tracker)
    return result


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Regenerate and re-upload one video")
    parser.add_argument("video_number", type=int)
    parser.add_argument("--skip-voiceover", action="store_true", help="Reuse existing MP3 if present")
    args = parser.parse_args()

    try:
        result = regenerate_and_reupload(args.video_number, skip_voiceover=args.skip_voiceover)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        logging.exception("Regenerate/reupload failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
