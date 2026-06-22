"""Shared helpers for parsing video script files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
VIDEO_SCRIPTS_DIR = PROJECT_ROOT / "video_scripts"
OUTPUT_DIR = PROJECT_ROOT / "output"
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGS_DIR = PROJECT_ROOT / "logs"

TIMESTAMP_PATTERN = re.compile(
    r"^(\d{1,2}:\d{2})-(\d{1,2}:\d{2})\s*-\s*(.+)$"
)


def script_path(video_number: int) -> Path:
    return VIDEO_SCRIPTS_DIR / f"video_{video_number}.txt"


def parse_header(content: str) -> dict[str, str]:
    """Parse TITLE, DESCRIPTION, and TAGS from script header."""
    header: dict[str, str] = {"title": "", "description": "", "tags": ""}
    for line in content.splitlines():
        upper = line.strip().upper()
        if upper.startswith("TITLE:"):
            header["title"] = line.split(":", 1)[1].strip()
        elif upper.startswith("DESCRIPTION:"):
            header["description"] = line.split(":", 1)[1].strip()
        elif upper.startswith("TAGS:"):
            header["tags"] = line.split(":", 1)[1].strip()
        elif upper.startswith("SCRIPT:"):
            break
    return header


def parse_script_section(content: str) -> str:
    """Return raw SCRIPT section (everything after SCRIPT: line)."""
    lines = content.splitlines()
    in_script = False
    script_lines: list[str] = []
    for line in lines:
        if line.strip().upper().startswith("SCRIPT:"):
            in_script = True
            continue
        if in_script:
            script_lines.append(line)
    return "\n".join(script_lines).strip()


def extract_voiceover_text(content: str) -> str:
    """Extract voiceover narration from SCRIPT section."""
    script = parse_script_section(content)
    if not script:
        raise ValueError("SCRIPT section is empty or missing")

    paragraphs: list[str] = []
    current: list[str] = []
    capture = False

    for line in script.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("voiceover:"):
            capture = True
            text = stripped.split(":", 1)[1].strip()
            if text:
                current.append(text)
            continue
        if stripped.lower().startswith("visual:"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            capture = False
            continue
        if capture and stripped:
            if TIMESTAMP_PATTERN.match(stripped):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                capture = False
                continue
            current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))

    voiceover = " ".join(paragraphs).strip()
    if not voiceover:
        raise ValueError("No Voiceover lines found in SCRIPT section")
    return voiceover


def parse_timestamps(content: str) -> list[dict[str, Any]]:
    """Parse timestamp ranges and section titles for on-screen overlays."""
    script = parse_script_section(content)
    segments: list[dict[str, Any]] = []

    for line in script.splitlines():
        match = TIMESTAMP_PATTERN.match(line.strip())
        if match:
            start, end, title = match.groups()
            segments.append(
                {
                    "start": _time_to_seconds(start),
                    "end": _time_to_seconds(end),
                    "title": title.strip(),
                }
            )
    return segments


def _time_to_seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    raise ValueError(f"Invalid timestamp format: {timestamp}")


def parse_tags(tags_line: str) -> list[str]:
    return [tag.strip() for tag in tags_line.split(",") if tag.strip()]
