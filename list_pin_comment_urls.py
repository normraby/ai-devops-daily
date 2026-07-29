#!/usr/bin/env python3
"""Print YouTube Studio deep-links to pin compliance comments (API cannot pin)."""

from __future__ import annotations

import json
from pathlib import Path

TRACKER = Path(__file__).resolve().parent / "tracker.json"
STATE = Path(__file__).resolve().parent / "playlist_state.json"


def main() -> None:
    tracker = json.loads(TRACKER.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    comments = state.get("comments", {})
    print("YouTube Data API cannot pin comments. Pin in Studio:")
    print("1) Open each URL while signed in as the channel owner")
    print("2) Find the AI DevOps compliance comment → ⋮ → Pin comment\n")
    for num in sorted(tracker.get("videos", {}), key=int):
        entry = tracker["videos"][num]
        if entry.get("status") != "uploaded":
            continue
        vid = entry["video_id"]
        studio = f"https://studio.youtube.com/video/{vid}/comments"
        has = "has_comment" if comments.get(vid) else "comment_missing"
        print(f"Video {num:>2} [{has}]: {studio}")


if __name__ == "__main__":
    main()
