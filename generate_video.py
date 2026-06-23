#!/usr/bin/env python3
"""Generate MP4 video from Pexels B-roll, voiceover, and lower-third titles."""

from __future__ import annotations

import argparse
import logging
import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import requests
from dotenv import load_dotenv
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx import Loop

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
LOWER_THIRD_HEIGHT = HEIGHT // 4  # bottom 25%
LOWER_THIRD_TOP = HEIGHT - LOWER_THIRD_HEIGHT
LOWER_THIRD_MARGIN_X = 80
TEXT_BASELINE_Y = HEIGHT - 90
MIN_CLIPS = 5
MAX_CLIPS = 8
CLIP_MIN_SEC = 10
CLIP_MAX_SEC = 15
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
BG_TOP = (13, 17, 23)  # #0D1117
BG_BOTTOM = (31, 41, 55)  # #1F2937
MIN_VALID_CLIPS = 2

# Title keyword -> Pexels search queries
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


def find_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    raise FileNotFoundError(
        "No suitable font found. Install DejaVu or Arial Bold on the system."
    )


def extract_title_keywords(title: str) -> list[str]:
    """Extract topic keywords from the script TITLE for Pexels searches."""
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

    # Prefer clips in the 10-15 second sweet spot (accept 8-30s).
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
    """Download 5-8 unique stock clips; cache globally under assets/pexels_cache/."""
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
            "Downloaded only %d/%d requested clips; will validate and may fall back to gradient",
            len(downloaded),
            num_clips,
        )

    return downloaded


def load_valid_videoclip(clip_path: Path) -> VideoFileClip | None:
    """Load a VideoFileClip and verify its reader returns valid frames."""
    clip: VideoFileClip | None = None
    try:
        clip = VideoFileClip(str(clip_path))
        clip = clip.without_audio()  # strip Pexels music — voiceover is the only audio track
        test_frame = clip.get_frame(0)
        if test_frame is None:
            raise ValueError("Empty frame")
        if clip.duration is None or clip.duration <= 0:
            raise ValueError("Invalid clip duration")
        # Catch truncated/corrupt downloads that only fail near the end.
        check_t = min(max(clip.duration - 0.1, 0.0), clip.duration / 2)
        mid_frame = clip.get_frame(check_t)
        if mid_frame is None:
            raise ValueError("Empty mid/end frame")
        return clip
    except Exception as exc:
        logging.warning("Skipping corrupt clip %s: %s", clip_path.name, exc)
        if clip is not None:
            clip.close()
        clip_path.unlink(missing_ok=True)
        return None


def validate_clip_paths(clip_paths: list[Path]) -> list[Path]:
    """Return only paths whose cached files load and decode successfully."""
    valid_paths: list[Path] = []
    for clip_path in clip_paths:
        clip = load_valid_videoclip(clip_path)
        if clip is None:
            continue
        clip.close()
        valid_paths.append(clip_path)
    return valid_paths


def make_gradient_background(duration: float) -> VideoClip:
    """Fallback background when stock footage is unavailable or corrupt."""

    def frame_function(t: float) -> np.ndarray:
        del t
        gradient = np.linspace(0, 1, HEIGHT)[:, np.newaxis]
        frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        for channel in range(3):
            top = BG_TOP[channel]
            bottom = BG_BOTTOM[channel]
            frame[:, :, channel] = (top + (bottom - top) * gradient).astype(np.uint8)
        return frame

    return VideoClip(frame_function, duration=duration)


def fit_clip_to_frame(clip: VideoFileClip) -> VideoFileClip:
    """Scale to cover 1920x1080 using separate width/height resize, then center-crop."""
    clip = clip.without_audio()
    source_w, source_h = clip.w, clip.h
    if source_w <= 0 or source_h <= 0:
        raise ValueError(f"Invalid clip dimensions: {source_w}x{source_h}")

    target_aspect = WIDTH / HEIGHT
    source_aspect = source_w / source_h

    if source_aspect > target_aspect:
        clip = clip.resized(height=HEIGHT)
        x_center = clip.w / 2
        clip = clip.cropped(x1=x_center - WIDTH / 2, x2=x_center + WIDTH / 2)
    else:
        clip = clip.resized(width=WIDTH)
        y_center = clip.h / 2
        clip = clip.cropped(y1=y_center - HEIGHT / 2, y2=y_center + HEIGHT / 2)

    return clip


def extract_clip_segment(source: VideoFileClip, duration: float, offset: float) -> VideoFileClip:
    """Take a 10-15s segment from source, looping if the file is shorter."""
    use_duration = min(max(duration, CLIP_MIN_SEC), CLIP_MAX_SEC)

    if source.duration >= use_duration:
        start = min(offset, max(0.0, source.duration - use_duration))
        segment = source.subclipped(start, start + use_duration)
    else:
        segment = source.with_effects([Loop(duration=use_duration)])

    return segment.with_duration(use_duration)


def build_stock_video(clip_paths: list[Path], total_duration: float) -> VideoFileClip:
    """Concatenate B-roll clips (cycling as needed) to match voiceover length."""
    valid_paths = validate_clip_paths(clip_paths)
    if len(valid_paths) < MIN_VALID_CLIPS:
        logging.warning(
            "Only %d valid Pexels clip(s) after validation — using gradient fallback",
            len(valid_paths),
        )
        return make_gradient_background(total_duration)

    segments: list[VideoFileClip] = []
    elapsed = 0.0
    path_index = 0
    max_iterations = int(total_duration / CLIP_MIN_SEC) + len(valid_paths) * 3

    while elapsed < total_duration - 0.05 and path_index < max_iterations:
        remaining = total_duration - elapsed
        target = min(random.uniform(CLIP_MIN_SEC, CLIP_MAX_SEC), remaining)
        target = max(target, min(CLIP_MIN_SEC, remaining))

        path = valid_paths[path_index % len(valid_paths)]
        source = load_valid_videoclip(path)
        path_index += 1
        if source is None:
            continue

        try:
            fitted = fit_clip_to_frame(source)
            segment = extract_clip_segment(fitted, target, offset=path_index * 2.5)
            segment = segment.without_audio()
            test_frame = segment.get_frame(0)
            if test_frame is None:
                raise ValueError("Empty segment frame")
            segments.append(segment)
            elapsed += segment.duration
        except Exception as exc:
            logging.warning("Failed to process clip %s: %s", path.name, exc)
            path.unlink(missing_ok=True)
        # Do not close source here — subclips share the parent's reader until render completes.

    if not segments:
        logging.warning("No valid segments built — using gradient fallback")
        return make_gradient_background(total_duration)

    background = concatenate_videoclips(segments, method="compose")
    if background.duration is None or background.duration <= 0:
        logging.warning("Concatenated clip has invalid duration — using gradient fallback")
        background.close()
        for segment in segments:
            segment.close()
        return make_gradient_background(total_duration)

    try:
        if background.get_frame(0) is None:
            raise ValueError("Concatenated clip returned empty frame")
    except Exception as exc:
        logging.warning("Concatenated clip failed frame test (%s) — using gradient fallback", exc)
        background.close()
        for segment in segments:
            segment.close()
        return make_gradient_background(total_duration)

    if background.duration > total_duration:
        background = background.subclipped(0, total_duration)
    # Ensure no Pexels background music survives into the final mux.
    return background.without_audio().with_duration(total_duration)


def build_dark_overlay(duration: float) -> ColorClip:
    return (
        ColorClip(size=(WIDTH, HEIGHT), color=(0, 0, 0))
        .with_opacity(OVERLAY_OPACITY)
        .with_duration(duration)
    )


def build_lower_third_gradient(duration: float) -> ImageClip:
    """Subtle dark gradient band in the bottom 25% of the frame."""
    rgb = np.zeros((LOWER_THIRD_HEIGHT, WIDTH, 3), dtype=np.uint8)
    alpha = np.linspace(0.0, 0.92, LOWER_THIRD_HEIGHT) ** 1.3
    mask = np.stack([alpha] * WIDTH, axis=1).astype(float)

    gradient = (
        ImageClip(rgb)
        .with_mask(ImageClip(mask, is_mask=True))
        .with_duration(duration)
        .with_position((0, LOWER_THIRD_TOP))
    )
    return gradient


def build_lower_third_text_clips(segments: list[dict], font: str) -> list[TextClip]:
    """White bold section titles in the bottom 25%, timed to voiceover segments."""
    clips: list[TextClip] = []

    for segment in segments:
        start = segment["start"]
        end = segment["end"]
        if end <= start:
            continue

        text = (
            TextClip(
                font=font,
                text=segment["title"],
                font_size=44,
                color="white",
                method="caption",
                size=(WIDTH - 160, None),
                text_align="left",
            )
            .with_start(start)
            .with_duration(end - start)
            .with_position((LOWER_THIRD_MARGIN_X, TEXT_BASELINE_Y))
        )
        clips.append(text)

    return clips


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
    cache_dir = PEXELS_CACHE_DIR

    font = find_font()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"video_{video_number}.mp4"

    logging.info("Generating video for video %s", video_number)
    logging.info("Title: %s", title)
    logging.info("Title keywords / search terms: %s", search_terms[:num_clips])
    logging.info("Segments: %d | Stock clips: %d", len(segments), num_clips)

    audio = AudioFileClip(str(audio_file))
    duration = audio.duration

    clip_paths = collect_pexels_clips(search_terms, api_key, num_clips, cache_dir)
    background = build_stock_video(clip_paths, duration)
    overlay = build_dark_overlay(duration)
    lower_gradient = build_lower_third_gradient(duration)
    lower_text = build_lower_third_text_clips(segments, font)

    video = CompositeVideoClip(
        [background, overlay, lower_gradient, *lower_text],
        size=(WIDTH, HEIGHT),
    ).with_audio(audio).with_duration(duration)

    logging.info("Rendering video (duration=%.1fs) to %s", duration, output_file)
    video.write_videofile(
        str(output_file),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    video.close()
    background.close()
    audio.close()

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"Video generation failed: {output_file}")

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logging.info("Video saved successfully (%.1f MB)", size_mb)
    return str(output_file)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Generate MP4 with Pexels B-roll")
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
