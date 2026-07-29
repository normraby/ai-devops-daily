#!/usr/bin/env python3
"""Refresh YouTube metadata for all uploaded AI DevOps Daily videos."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from upload_to_youtube import TRACKER_FILE, load_tracker, update_video_metadata

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])


def uploaded_numbers(tracker: dict) -> list[int]:
    numbers: list[int] = []
    for key, entry in tracker.get("videos", {}).items():
        if entry.get("status") == "uploaded" and entry.get("video_id"):
            numbers.append(int(key))
    return sorted(numbers)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Refresh metadata for uploaded AI DevOps Daily videos")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tracker = load_tracker()
    numbers = [n for n in uploaded_numbers(tracker) if args.start <= n <= args.end]
    logging.info("Refreshing metadata for videos: %s", numbers)

    for num in numbers:
        if args.dry_run:
            logging.info("[dry-run] Would update metadata for video %s", num)
            continue
        try:
            update_video_metadata(num)
        except Exception as exc:
            logging.error("Failed video %s: %s", num, exc)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
