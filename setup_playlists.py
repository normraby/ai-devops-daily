#!/usr/bin/env python3
"""Create/update YouTube playlists and add uploaded videos from tracker.json."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from googleapiclient.discovery import build

from description_builder import build_pinned_comment
from google_auth import load_credentials
from script_utils import parse_header, script_path

PROJECT_ROOT = Path(__file__).resolve().parent
TRACKER_FILE = PROJECT_ROOT / "tracker.json"
PLAYLIST_STATE = PROJECT_ROOT / "playlist_state.json"

PLAYLISTS = [
    ("CI/CD & Platform Engineering", range(1, 6)),
    ("Cloud Cost & Security", range(6, 11)),
    ("GitOps & Kubernetes", range(11, 16)),
    ("AI Agents & SRE", range(16, 21)),
]

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def load_tracker() -> dict:
    return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))


def load_state() -> dict:
    if PLAYLIST_STATE.exists():
        return json.loads(PLAYLIST_STATE.read_text(encoding="utf-8"))
    return {"playlists": {}, "comments": {}}


def save_state(state: dict) -> None:
    PLAYLIST_STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def ensure_playlist(youtube, title: str, state: dict) -> str:
    existing = state["playlists"].get(title)
    if existing:
        return existing
    body = {
        "snippet": {
            "title": title,
            "description": f"{title} — curated episodes from AI DevOps Daily. Educational content.",
        },
        "status": {"privacyStatus": "public"},
    }
    resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
    playlist_id = resp["id"]
    if not playlist_id or len(playlist_id) < 10:
        raise RuntimeError(f"Unexpected playlist id from API: {resp!r}")
    state["playlists"][title] = playlist_id
    save_state(state)
    logging.info("Created playlist %s → %s", title, playlist_id)
    time.sleep(2)
    return playlist_id


def playlist_has_video(youtube, playlist_id: str, video_id: str) -> bool:
    request = youtube.playlistItems().list(
        part="contentDetails", playlistId=playlist_id, maxResults=50
    )
    while request is not None:
        resp = request.execute()
        for item in resp.get("items", []):
            if item["contentDetails"]["videoId"] == video_id:
                return True
        request = youtube.playlistItems().list_next(request, resp)
    return False


def add_to_playlist(youtube, playlist_id: str, video_id: str) -> None:
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    try:
        youtube.playlistItems().insert(part="snippet", body=body).execute()
        logging.info("Added %s to playlist %s", video_id, playlist_id)
    except Exception as exc:
        # Duplicate or eventual-consistency after create — treat as non-fatal
        msg = str(exc)
        if "already" in msg.lower() or "duplicate" in msg.lower():
            logging.info("Already in playlist: %s", video_id)
            return
        logging.warning("Could not add %s to %s: %s", video_id, playlist_id, exc)


def post_top_comment(youtube, video_id: str, text: str, state: dict) -> None:
    if state["comments"].get(video_id):
        logging.info("Comment already posted for %s", video_id)
        return
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}},
        }
    }
    resp = youtube.commentThreads().insert(part="snippet", body=body).execute()
    state["comments"][video_id] = resp["id"]
    logging.info("Posted compliance comment on %s (pin manually in Studio if desired)", video_id)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stderr)])
    youtube = build("youtube", "v3", credentials=load_credentials())
    tracker = load_tracker()
    state = load_state()
    videos = tracker.get("videos", {})

    for title, numbers in PLAYLISTS:
        playlist_id = ensure_playlist(youtube, title, state)
        for num in numbers:
            entry = videos.get(str(num), {})
            video_id = entry.get("video_id")
            if not video_id or entry.get("status") != "uploaded":
                continue
            add_to_playlist(youtube, playlist_id, video_id)
            script = script_path(num)
            if script.exists():
                header = parse_header(script.read_text(encoding="utf-8"))
                title_txt = header.get("title") or f"Episode {num}"
                post_top_comment(youtube, video_id, build_pinned_comment(num, title_txt), state)

    save_state(state)
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
