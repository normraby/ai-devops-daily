#!/usr/bin/env python3
"""Upload generated video and thumbnail to YouTube with OAuth2."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from google_auth import load_credentials
from script_utils import LOGS_DIR, OUTPUT_DIR, parse_header, parse_tags, script_path

CLIENT_SECRET_FILE = Path(__file__).resolve().parent / "client_secret.json"
TOKEN_FILE = Path(__file__).resolve().parent / "token.json"
UPLOAD_LOG = LOGS_DIR / "upload_log.txt"
CATEGORY_ID = "28"
PRIVACY_STATUS = "public"
MAX_RETRIES = 3
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

DESCRIPTION_FOOTER = """

---
Original educational content by AI DevOps Daily. Code examples and diagrams are authored for teaching standard DevOps patterns. Illustrative metrics and scenarios are explained in the narration — not third-party survey data. We are not affiliated with vendors mentioned. Not financial, legal, or professional advice.
"""


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(UPLOAD_LOG),
        ],
    )


def get_authenticated_service():
    return build("youtube", "v3", credentials=load_credentials())


def append_upload_log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with UPLOAD_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def upload_video_with_retry(youtube, video_path: Path, metadata: dict) -> str:
    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": CATEGORY_ID,
        },
        "status": {"privacyStatus": PRIVACY_STATUS},
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info("Upload attempt %d/%d for %s", attempt, MAX_RETRIES, video_path.name)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logging.info("Upload progress: %.1f%%", status.progress() * 100)

            video_id = response["id"]
            logging.info("Upload complete. Video ID: %s", video_id)
            return video_id
        except HttpError as exc:
            logging.error("YouTube API error on attempt %d: %s", attempt, exc)
            if attempt == MAX_RETRIES:
                raise
            backoff = 2 ** attempt
            logging.info("Retrying in %d seconds...", backoff)
            time.sleep(backoff)
        except Exception as exc:
            logging.error("Upload failed on attempt %d: %s", attempt, exc)
            if attempt == MAX_RETRIES:
                raise
            backoff = 2 ** attempt
            logging.info("Retrying in %d seconds...", backoff)
            time.sleep(backoff)

    raise RuntimeError("Upload failed after retries")


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> None:
    if not thumbnail_path.exists():
        logging.warning("Thumbnail not found: %s", thumbnail_path)
        return

    media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
    logging.info("Thumbnail set for video %s", video_id)


def upload_to_youtube(video_number: int) -> dict:
    script_file = script_path(video_number)
    video_file = OUTPUT_DIR / f"video_{video_number}.mp4"
    thumbnail_file = OUTPUT_DIR / f"thumbnail_{video_number}.jpg"

    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_file}")
    if not video_file.exists():
        raise FileNotFoundError(f"Video not found: {video_file}")

    content = script_file.read_text(encoding="utf-8")
    header = parse_header(content)
    metadata = {
        "title": header.get("title") or f"AI DevOps Daily #{video_number}",
        "description": (header.get("description") or "AI DevOps Daily — automation insights for platform engineers.") + DESCRIPTION_FOOTER,
        "tags": parse_tags(header.get("tags", "")),
    }

    logging.info("Uploading video %s: %s", video_number, metadata["title"])
    youtube = get_authenticated_service()
    video_id = upload_video_with_retry(youtube, video_file, metadata)
    try:
        set_thumbnail(youtube, video_id, thumbnail_file)
    except Exception as thumb_err:
        logging.warning(
            "Thumbnail upload skipped (channel may need YouTube verification): %s",
            thumb_err,
        )

    result = {
        "video_number": video_number,
        "video_id": video_id,
        "title": metadata["title"],
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }

    append_upload_log(
        f"SUCCESS video={video_number} id={video_id} title={metadata['title']} url={result['url']}"
    )
    logging.info("Upload successful: %s", result["url"])
    return result


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("video_number", type=int, help="Video number (e.g. 1)")
    args = parser.parse_args()

    try:
        result = upload_to_youtube(args.video_number)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        append_upload_log(f"FAILURE video={args.video_number} error={exc}")
        logging.exception("YouTube upload failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
