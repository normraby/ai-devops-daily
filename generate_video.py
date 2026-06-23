#!/usr/bin/env python3
"""Generate MP4 video from Pexels B-roll via ffmpeg (CI-friendly, low memory)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from script_utils import (
    ASSETS_DIR,
    OUTPUT_DIR,
    parse_header,
    parse_timestamps,
    script_path,
)

PROJECT_ROOT = Path(__file__).resolve().parent
PEXELS_CACHE_DIR = ASSETS_DIR / "pexels_cache"

WIDTH, HEIGHT = 1920, 1080
FPS = 24
OVERLAY_OPACITY = 0.55
MIN_CLIPS = 5
MAX_CLIPS = 8
CLIP_MIN_SEC = 10
CLIP_MAX_SEC = 15
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
MIN_VALID_CLIPS = 2

TOPIC_SEARCH_MAP: dict[str, list[str]] = {
    "jenkins": ["jenkins software pipeline", "coding automation server"],
    "terraform": ["terraform infrastructure", "data center cloud servers"],
    "kubernetes": ["kubernetes containers", "data center server room"],
    "gitops": ["git software development", "devops programming"],
    "ansible": ["server room network", "it infrastructure automation"],
    "finops": ["cloud cost analytics", "data center finance technology"],
    "security": ["cybersecurity server room", "network security technology"],
    "devsecops": ["secure coding programming", "cybersecurity technology"],
    "observability": ["monitoring dashboard server", "network operations center"],
    "incident": ["network operations center", "server monitoring alert"],
    "testing": ["software testing laptop", "qa programming code"],
    "database": ["database server room", "data storage technology"],
    "platform": ["software engineering office", "developer team technology"],
    "agents": ["artificial intelligence technology", "ai automation data"],
    "agent": ["artificial intelligence technology", "ai automation data"],
    "cloud": ["cloud computing data center", "server infrastructure network"],
    "pipeline": ["ci cd pipeline", "software development automation"],
    "docker": ["container server technology", "cloud infrastructure"],
    "sre": ["site reliability server monitoring", "data center operations"],
    "chatops": ["team collaboration technology", "developer slack office"],
    "capacity": ["data center servers scaling", "cloud infrastructure growth"],
    "multi-cloud": ["multi cloud network", "global data center"],
    "benchmark": ["technology data analytics", "software performance testing"],
    "ci/cd": ["ci cd pipeline automation", "continuous integration software"],
    "ci cd": ["ci cd pipeline automation", "continuous integration software"],
    "devops": ["devops programming team", "software pipeline automation"],
    "ai": ["artificial intelligence technology", "machine learning servers"],
    "qa": ["software quality testing", "programming code review"],
    "code review": ["programming code screen", "software developer review"],
    "tutorial": ["programming tutorial laptop", "coding developer screen"],
}

DEFAULT_SEARCH_TERMS = [
    "data center servers",
    "programming code screen",
    "software pipeline technology",
    "server room network",
    "cloud computing infrastructure",
    "devops automation",
    "technology office coding",
    "network operations center",
]

TITLE_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "your", "that", "this",
    "what", "when", "how", "why", "are", "is", "in", "of", "to", "a", "an",
    "vs", "vs.", "don't", "lie", "explained", "future", "beyond", "daily",
    "death", "dying", "rise", "numbers", "never", "again", "first", "step",
    "case", "study", "modern", "modernization", "predictions", "building",
}


def setup_logging() -> None:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / "video_log.txt"),
        ],
    )


def load_pexels_api_key() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        raise EnvironmentError(
            "PEXELS_API_KEY not set. Add your free key to .env "
            "(https://www.pexels.com/api/)"
        )
    return api_key


def ffmpeg_preset() -> str:
    return "ultrafast" if os.getenv("CI") else "medium"


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", *args]
    logging.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg command failed")


def get_media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))


def find_font_name() -> str:
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu Sans"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "Liberation Sans"),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "Arial"),
        ("/Library/Fonts/Arial Bold.ttf", "Arial"),
    ]
    for path, name in candidates:
        if Path(path).exists():
            return name
    return "Sans"


def extract_title_keywords(title: str) -> list[str]:
    title_lower = title.lower()
    queries: list[str] = []

    if "ci/cd" in title_lower:
        queries.extend(TOPIC_SEARCH_MAP["ci/cd"])
    if "ci cd" in title_lower:
        queries.extend(TOPIC_SEARCH_MAP["ci cd"])

    for keyword, search_queries in TOPIC_SEARCH_MAP.items():
        if keyword in title_lower:
            queries.extend(search_queries)

    for token in re.findall(r"[A-Za-z][A-Za-z0-9/+-]*", title):
        normalized = token.lower().strip("/")
        if normalized in TITLE_STOPWORDS or len(normalized) < 3:
            continue
        if normalized in TOPIC_SEARCH_MAP:
            continue
        queries.append(normalized.replace("-", " "))

    if not queries:
        queries = DEFAULT_SEARCH_TERMS.copy()

    seen: set[str] = set()
    unique: list[str] = []
    for term in queries:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return unique


def pick_video_file_url(video: dict) -> str | None:
    files = video.get("video_files") or []
    if not files:
        return None
    landscape = [f for f in files if f.get("width", 0) >= f.get("height", 0)]
    candidates = landscape or files
    candidates.sort(key=lambda f: (f.get("width", 0), f.get("height", 0)), reverse=True)
    for candidate in candidates:
        link = candidate.get("link")
        if link:
            return link
    return None


def search_pexels_videos(query: str, api_key: str, per_page: int = 20) -> list[dict]:
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": per_page, "orientation": "landscape"}
    logging.info("Searching Pexels for: %s", query)
    response = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    videos = response.json().get("videos") or []
    preferred = [
        v for v in videos
        if CLIP_MIN_SEC - 2 <= v.get("duration", 0) <= CLIP_MAX_SEC + 15
    ]
    return preferred or videos


def download_pexels_clip(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        logging.info("Using cached clip: %s", destination.name)
        return destination

    logging.info("Downloading clip -> %s", destination.name)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError(f"Failed to download clip: {url}")
    return destination


def collect_pexels_clips(
    search_terms: list[str],
    api_key: str,
    num_clips: int,
    cache_dir: Path,
) -> list[Path]:
    downloaded: list[Path] = []
    used_ids: set[int] = set()
    term_index = 0
    attempts = 0
    max_attempts = max(len(search_terms) * 5, 20)

    while len(downloaded) < num_clips and attempts < max_attempts:
        query = search_terms[term_index % len(search_terms)]
        term_index += 1
        attempts += 1

        try:
            videos = search_pexels_videos(query, api_key)
        except requests.RequestException as exc:
            logging.warning("Pexels search failed for '%s': %s", query, exc)
            continue

        random.shuffle(videos)
        for video in videos:
            video_id = video.get("id")
            if video_id in used_ids:
                continue
            file_url = pick_video_file_url(video)
            if not file_url:
                continue

            suffix = Path(urlparse(file_url).path).suffix or ".mp4"
            destination = cache_dir / f"pexels_{video_id}{suffix}"
            try:
                download_pexels_clip(file_url, destination)
            except (requests.RequestException, RuntimeError) as exc:
                logging.warning("Clip download failed (id=%s): %s", video_id, exc)
                continue

            used_ids.add(video_id)
            downloaded.append(destination)
            logging.info(
                "Collected clip %d/%d (Pexels id=%s, duration=%ss)",
                len(downloaded),
                num_clips,
                video_id,
                video.get("duration", "?"),
            )
            break

    if len(downloaded) < MIN_CLIPS:
        logging.warning(
            "Downloaded only %d/%d requested clips; may fall back to solid background",
            len(downloaded),
            num_clips,
        )
    return downloaded


def probe_video_file(clip_path: Path) -> bool:
    try:
        return get_media_duration(clip_path) > 0
    except Exception as exc:
        logging.warning("ffprobe rejected %s: %s", clip_path.name, exc)
        return False


def validate_clip_paths(clip_paths: list[Path]) -> list[Path]:
    valid: list[Path] = []
    for clip_path in clip_paths:
        if probe_video_file(clip_path):
            valid.append(clip_path)
        else:
            logging.warning("Removing invalid cached clip: %s", clip_path.name)
            clip_path.unlink(missing_ok=True)
    return valid


def prepare_segment(
    source: Path,
    output: Path,
    segment_duration: float,
    start_offset: float,
) -> None:
    """Trim, loop, scale, crop, and strip audio from one B-roll segment."""
    source_duration = get_media_duration(source)
    preset = ffmpeg_preset()
    scale_crop = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT}"
    )

    cmd = ["-y", "-an"]
    if start_offset > 0:
        cmd.extend(["-ss", str(start_offset)])
    if source_duration < segment_duration:
        cmd.extend(["-stream_loop", "-1"])
    cmd.extend([
        "-i", str(source),
        "-t", str(segment_duration),
        "-vf", scale_crop,
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        str(output),
    ])
    run_ffmpeg(cmd)


def build_solid_background(output: Path, duration: float) -> None:
    preset = ffmpeg_preset()
    run_ffmpeg([
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x0D1117:s={WIDTH}x{HEIGHT}:r={FPS}",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        str(output),
    ])


def build_broll_video(
    clip_paths: list[Path],
    total_duration: float,
    work_dir: Path,
) -> Path:
    valid_paths = validate_clip_paths(clip_paths)
    concat_out = work_dir / "broll_concat.mp4"

    if len(valid_paths) < MIN_VALID_CLIPS:
        logging.warning("Using solid background fallback")
        build_solid_background(concat_out, total_duration)
        return concat_out

    segment_files: list[Path] = []
    elapsed = 0.0
    path_index = 0
    max_iterations = int(total_duration / CLIP_MIN_SEC) + len(valid_paths) * 3

    while elapsed < total_duration - 0.05 and path_index < max_iterations:
        remaining = total_duration - elapsed
        target = min(random.uniform(CLIP_MIN_SEC, CLIP_MAX_SEC), remaining)
        target = max(target, min(CLIP_MIN_SEC, remaining))

        source = valid_paths[path_index % len(valid_paths)]
        path_index += 1
        segment_path = work_dir / f"segment_{len(segment_files):03d}.mp4"

        try:
            prepare_segment(source, segment_path, target, offset=path_index * 2.5)
            segment_files.append(segment_path)
            elapsed += target
        except Exception as exc:
            logging.warning("Failed to prepare segment from %s: %s", source.name, exc)
            source.unlink(missing_ok=True)

    if not segment_files:
        logging.warning("No segments built — using solid background fallback")
        build_solid_background(concat_out, total_duration)
        return concat_out

    list_file = work_dir / "concat.txt"
    with list_file.open("w", encoding="utf-8") as handle:
        for segment in segment_files:
            handle.write(f"file '{segment.resolve()}'\n")

    preset = ffmpeg_preset()
    try:
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(concat_out),
        ])
    except RuntimeError:
        logging.info("Concat copy failed — re-encoding segments")
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p",
            str(concat_out),
        ])

    return concat_out


def seconds_to_ass(timestamp: float) -> str:
    hours = int(timestamp // 3600)
    minutes = int((timestamp % 3600) // 60)
    seconds = timestamp % 60
    return f"{hours}:{minutes:02d}:{seconds:05.2f}"


def escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")


def write_ass_subtitles(segments: list[dict], ass_path: Path, font_name: str) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: LowerThird,{font_name},44,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,3,1,0,1,80,80,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for segment in segments:
        start = segment["start"]
        end = segment["end"]
        if end <= start:
            continue
        title = escape_ass_text(segment["title"])
        events.append(
            f"Dialogue: 0,{seconds_to_ass(start)},{seconds_to_ass(end)},LowerThird,,0,0,0,,{title}"
        )

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def render_final_video(
    broll_video: Path,
    ass_path: Path,
    audio_path: Path,
    output_path: Path,
    duration: float,
) -> None:
    preset = ffmpeg_preset()
    ass_filter = str(ass_path.resolve()).replace("\\", "\\\\").replace(":", "\\:")
    opacity = OVERLAY_OPACITY
    filter_complex = (
        f"color=c=black@{opacity}:s={WIDTH}x{HEIGHT}:d={duration}[blk];"
        f"[0:v][blk]overlay=format=auto[vdim];"
        f"[vdim]ass='{ass_filter}'[vout]"
    )

    run_ffmpeg([
        "-y",
        "-i", str(broll_video),
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ])


def generate_video(video_number: int) -> str:
    script_file = script_path(video_number)
    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_file}")

    audio_file = OUTPUT_DIR / f"video_{video_number}.mp3"
    if not audio_file.exists():
        raise FileNotFoundError(
            f"Voiceover not found: {audio_file}. Run generate_voiceover.py first."
        )

    api_key = load_pexels_api_key()
    content = script_file.read_text(encoding="utf-8")
    header = parse_header(content)
    title = header.get("title") or f"AI DevOps Daily #{video_number}"
    segments = parse_timestamps(content)

    search_terms = extract_title_keywords(title)
    num_clips = min(MAX_CLIPS, max(MIN_CLIPS, min(len(segments), MAX_CLIPS) if segments else 6))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"video_{video_number}.mp4"
    duration = get_media_duration(audio_file)

    logging.info("Generating video for video %s", video_number)
    logging.info("Title: %s", title)
    logging.info("Duration: %.1fs | Stock clips: %d", duration, num_clips)
    logging.info("Render engine: ffmpeg (%s preset)", ffmpeg_preset())

    clip_paths = collect_pexels_clips(search_terms, api_key, num_clips, PEXELS_CACHE_DIR)
    work_dir = Path(tempfile.mkdtemp(prefix=f"video_{video_number}_", dir=OUTPUT_DIR))

    try:
        broll_video = build_broll_video(clip_paths, duration, work_dir)
        ass_path = work_dir / "lower_thirds.ass"
        write_ass_subtitles(segments, ass_path, find_font_name())
        render_final_video(broll_video, ass_path, audio_file, output_file, duration)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"Video generation failed: {output_file}")

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logging.info("Video saved successfully (%.1f MB)", size_mb)
    return str(output_file)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Generate MP4 with Pexels B-roll (ffmpeg)")
    parser.add_argument("video_number", type=int, help="Video number (e.g. 3)")
    args = parser.parse_args()

    try:
        generate_video(args.video_number)
        return 0
    except Exception as exc:
        logging.exception("Video generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
