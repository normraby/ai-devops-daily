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

from description_builder import build_description
from google_auth import load_credentials
from script_utils import LOGS_DIR, OUTPUT_DIR, parse_header, parse_tags, script_path

CLIENT_SECRET_FILE = Path(__file__).resolve().parent / "client_secret.json"
TOKEN_FILE = Path(__file__).resolve().parent / "token.json"
TRACKER_FILE = Path(__file__).resolve().parent / "tracker.json"
UPLOAD_LOG = LOGS_DIR / "upload_log.txt"
CATEGORY_ID = "28"
PRIVACY_STATUS = "public"
MAX_RETRIES = 3
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


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


def load_tracker() -> dict:
    if not TRACKER_FILE.exists():
        return {"last_uploaded": 0, "videos": {}}
    return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))


def resolve_video_id(video_number: int, video_id: str | None = None) -> str:
    if video_id:
        return video_id
    entry = load_tracker().get("videos", {}).get(str(video_number), {})
    vid = entry.get("video_id", "")
    if not vid:
        raise ValueError(
            f"No YouTube video_id for video {video_number} in tracker.json. "
            "Upload the video first or pass --video-id."
        )
    return vid


def _build_metadata(video_number: int, content: str, header: dict[str, str]) -> dict:
    title = header.get("title") or f"AI DevOps Daily #{video_number}"
    return {
        "title": title,
        "description": build_description(video_number, content, {**header, "title": title}),
        "tags": parse_tags(header.get("tags", "")),
    }


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


def update_video_metadata(video_number: int, *, video_id: str | None = None) -> dict:
    script_file = script_path(video_number)
    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_file}")

    content = script_file.read_text(encoding="utf-8")
    header = parse_header(content)
    metadata = _build_metadata(video_number, content, header)

    resolved_id = resolve_video_id(video_number, video_id)
    logging.info("Updating metadata for video %s (YouTube ID: %s)", video_number, resolved_id)
    youtube = get_authenticated_service()

    current = youtube.videos().list(part="snippet", id=resolved_id).execute()
    items = current.get("items", [])
    if not items:
        raise ValueError(f"YouTube video not found: {resolved_id}")

    snippet = items[0]["snippet"]
    snippet["title"] = metadata["title"]
    snippet["description"] = metadata["description"]
    snippet["tags"] = metadata["tags"]
    snippet["categoryId"] = CATEGORY_ID

    youtube.videos().update(part="snippet", body={"id": resolved_id, "snippet": snippet}).execute()

    url = f"https://www.youtube.com/watch?v={resolved_id}"
    result = {
        "video_number": video_number,
        "video_id": resolved_id,
        "title": metadata["title"],
        "url": url,
        "action": "metadata_update",
    }
    append_upload_log(
        f"METADATA video={video_number} id={resolved_id} title={metadata['title']} url={url}"
    )
    logging.info("Metadata updated for %s", url)
    return result


def set_thumbnail_only(video_number: int, *, video_id: str | None = None) -> dict:
    thumbnail_file = OUTPUT_DIR / f"thumbnail_{video_number}.jpg"
    if not thumbnail_file.exists():
        raise FileNotFoundError(f"Thumbnail not found: {thumbnail_file}")

    resolved_id = resolve_video_id(video_number, video_id)
    logging.info("Setting thumbnail for video %s (YouTube ID: %s)", video_number, resolved_id)
    youtube = get_authenticated_service()
    set_thumbnail(youtube, resolved_id, thumbnail_file)

    url = f"https://www.youtube.com/watch?v={resolved_id}"
    result = {
        "video_number": video_number,
        "video_id": resolved_id,
        "url": url,
        "thumbnail": str(thumbnail_file),
        "action": "thumbnail_only",
    }
    append_upload_log(f"THUMBNAIL video={video_number} id={resolved_id} file={thumbnail_file.name}")
    logging.info("Thumbnail set for %s", url)
    return result


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
    metadata = _build_metadata(video_number, content, header)

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
    parser.add_argument(
        "--thumbnail-only",
        action="store_true",
        help="Set custom thumbnail on an already-uploaded video",
    )
    parser.add_argument(
        "--update-metadata",
        action="store_true",
        help="Update title, description, and tags on an already-uploaded video",
    )
    parser.add_argument("--video-id", default=None, help="YouTube video ID override")
    args = parser.parse_args()

    try:
        if args.thumbnail_only:
            result = set_thumbnail_only(args.video_number, video_id=args.video_id)
        elif args.update_metadata:
            result = update_video_metadata(args.video_number, video_id=args.video_id)
        else:
            result = upload_to_youtube(args.video_number)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        append_upload_log(f"FAILURE video={args.video_number} error={exc}")
        logging.exception("YouTube upload failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
