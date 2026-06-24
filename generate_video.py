#!/usr/bin/env python3
"""Generate MP4 from script Visual: directions — diagrams, charts, documentation slides."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from script_utils import OUTPUT_DIR, parse_header, parse_segments, script_path
from visual_slides import render_segment_slide

PROJECT_ROOT = Path(__file__).resolve().parent

WIDTH, HEIGHT = 1920, 1080
FPS = 24
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(logs_dir / "video_log.txt"),
        ],
    )


def ffmpeg_preset() -> str:
    return "ultrafast" if os.getenv("CI") else "medium"


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", *args]
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


def render_slide_image(segment: dict, episode_title: str, tags: str, output_path: Path) -> None:
    slide = render_segment_slide(segment, episode_title, tags)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    slide.save(output_path, format="PNG", optimize=True)


def slide_to_clip(slide_path: Path, duration: float, output_path: Path) -> None:
    """Convert a static slide to a short video clip with subtle zoom."""
    preset = ffmpeg_preset()
    frames = max(int(duration * FPS), 1)
    zoom_rate = 0.0004 if duration > 10 else 0.0008
    max_zoom = 1.06
    run_ffmpeg([
        "-y",
        "-loop", "1",
        "-i", str(slide_path),
        "-vf", (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='min(zoom+{zoom_rate},{max_zoom})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
        ),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ])


def concat_clips(clip_paths: list[Path], output_path: Path) -> None:
    list_file = output_path.with_suffix(".txt")
    with list_file.open("w", encoding="utf-8") as handle:
        for clip in clip_paths:
            handle.write(f"file '{clip.resolve()}'\n")

    preset = ffmpeg_preset()
    try:
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(output_path),
        ])
    except RuntimeError:
        logging.info("Concat copy failed — re-encoding slide clips")
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p",
            str(output_path),
        ])
    finally:
        list_file.unlink(missing_ok=True)


def mux_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    preset = ffmpeg_preset()
    run_ffmpeg([
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ])


def build_slide_video(
    segments: list[dict],
    episode_title: str,
    total_duration: float,
    work_dir: Path,
    tags: str = "",
) -> Path:
    if not segments:
        raise ValueError("No script segments found — check SCRIPT section format")

    script_duration = segments[-1]["end"] - segments[0]["start"]
    scale = total_duration / script_duration if script_duration > 0 else 1.0
    logging.info("Scaling slide durations by %.2fx to match audio (%.1fs)", scale, total_duration)

    slides_dir = work_dir / "slides"
    clips_dir = work_dir / "clips"
    slides_dir.mkdir()
    clips_dir.mkdir()

    clip_paths: list[Path] = []
    for index, segment in enumerate(segments):
        duration = max((segment["end"] - segment["start"]) * scale, 1.0)
        slide_path = slides_dir / f"slide_{index:03d}.png"
        clip_path = clips_dir / f"clip_{index:03d}.mp4"

        logging.info(
            "Rendering slide %d/%d: %s (%.1fs)",
            index + 1,
            len(segments),
            segment["title"][:60],
            duration,
        )
        render_slide_image(segment, episode_title, tags, slide_path)
        slide_to_clip(slide_path, duration, clip_path)
        clip_paths.append(clip_path)

    concat_out = work_dir / "slides_concat.mp4"
    concat_clips(clip_paths, concat_out)
    return concat_out


def generate_video(video_number: int) -> str:
    script_file = script_path(video_number)
    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_file}")

    audio_file = OUTPUT_DIR / f"video_{video_number}.mp3"
    if not audio_file.exists():
        raise FileNotFoundError(
            f"Voiceover not found: {audio_file}. Run generate_voiceover.py first."
        )

    content = script_file.read_text(encoding="utf-8")
    header = parse_header(content)
    episode_title = header.get("title") or f"AI DevOps Daily #{video_number}"
    tags = header.get("tags", "")
    segments = parse_segments(content)

    if not segments:
        raise ValueError(f"No timestamp segments in {script_file}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"video_{video_number}.mp4"
    duration = get_media_duration(audio_file)

    logging.info("Generating slide-based video for video %s", video_number)
    logging.info("Title: %s", episode_title)
    logging.info("Segments: %d | Audio duration: %.1fs", len(segments), duration)
    logging.info("Render engine: Pillow + matplotlib + ffmpeg (%s preset)", ffmpeg_preset())

    work_dir = Path(tempfile.mkdtemp(prefix=f"video_{video_number}_", dir=OUTPUT_DIR))
    silent_video = work_dir / "silent.mp4"

    try:
        slide_video = build_slide_video(segments, episode_title, duration, work_dir, tags)
        mux_audio(slide_video, audio_file, output_file)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"Video generation failed: {output_file}")

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logging.info("Video saved successfully (%.1f MB)", size_mb)
    return str(output_file)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Generate MP4 from documentation-style slides")
    parser.add_argument("video_number", type=int, help="Video number (e.g. 6)")
    args = parser.parse_args()

    try:
        generate_video(args.video_number)
        return 0
    except Exception as exc:
        logging.exception("Video generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
