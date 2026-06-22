#!/usr/bin/env python3
"""Generate MP4 video from script, voiceover, and optional logo watermark."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, TextClip, VideoClip

from script_utils import (
    ASSETS_DIR,
    OUTPUT_DIR,
    parse_header,
    parse_timestamps,
    script_path,
)

WIDTH, HEIGHT = 1920, 1080
FPS = 24
TITLE_DURATION = 5.0
BG_TOP = (13, 17, 23)  # #0D1117
BG_BOTTOM = (31, 41, 55)  # #1F2937
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / "video_log.txt"),
        ],
    )


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


def make_gradient_clip(duration: float) -> VideoClip:
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


def build_title_clip(title: str, font: str) -> TextClip:
    return (
        TextClip(
            font=font,
            text=title,
            font_size=72,
            color="white",
            method="caption",
            size=(WIDTH - 200, None),
            text_align="center",
        )
        .with_duration(TITLE_DURATION)
        .with_position("center")
    )


def build_segment_clips(segments: list[dict], font: str) -> list[TextClip]:
    clips: list[TextClip] = []
    for index, segment in enumerate(segments, start=1):
        start = max(segment["start"], TITLE_DURATION)
        end = segment["end"]
        if end <= start:
            continue
        bullet_text = f"• {segment['title']}"
        clip = (
            TextClip(
                font=font,
                text=bullet_text,
                font_size=42,
                color="white",
                method="caption",
                size=(WIDTH - 240, None),
                text_align="left",
            )
            .with_start(start)
            .with_duration(end - start)
            .with_position(("center", 720 + index * 8))
        )
        clips.append(clip)
    return clips


def build_watermark(duration: float) -> ImageClip | None:
    logo_path = ASSETS_DIR / "logo.png"
    if not logo_path.exists():
        logging.info("Logo not found at %s — skipping watermark", logo_path)
        return None

    logo = (
        ImageClip(str(logo_path))
        .resized(height=80)
        .with_duration(duration)
        .with_opacity(0.75)
        .with_position((WIDTH - 140, HEIGHT - 100))
    )
    logging.info("Applied logo watermark from %s", logo_path)
    return logo


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
    title = header.get("title") or f"AI DevOps Daily #{video_number}"
    segments = parse_timestamps(content)

    font = find_font()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"video_{video_number}.mp4"

    logging.info("Generating video for video %s", video_number)
    logging.info("Title: %s", title)
    logging.info("Segments: %d", len(segments))

    audio = AudioFileClip(str(audio_file))
    duration = audio.duration

    background = make_gradient_clip(duration)
    title_clip = build_title_clip(title, font)
    segment_clips = build_segment_clips(segments, font)
    watermark = build_watermark(duration)

    layers = [background, title_clip, *segment_clips]
    if watermark is not None:
        layers.append(watermark)

    video = CompositeVideoClip(layers, size=(WIDTH, HEIGHT)).with_audio(audio)
    video = video.with_duration(duration)

    logging.info("Rendering video (duration=%.1fs) to %s", duration, output_file)
    video.write_videofile(
        str(output_file),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    video.close()
    audio.close()

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"Video generation failed: {output_file}")

    logging.info("Video saved successfully (%d bytes)", output_file.stat().st_size)
    return str(output_file)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Generate MP4 video from script")
    parser.add_argument("video_number", type=int, help="Video number (e.g. 1)")
    args = parser.parse_args()

    try:
        generate_video(args.video_number)
        return 0
    except Exception as exc:
        logging.exception("Video generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
