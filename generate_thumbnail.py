#!/usr/bin/env python3
"""Generate YouTube thumbnail from video script title."""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from script_utils import ASSETS_DIR, OUTPUT_DIR, parse_header, script_path

WIDTH, HEIGHT = 1280, 720
BG_COLOR = (13, 17, 23)  # #0D1117
ACCENT_COLOR = (255, 0, 0)  # #FF0000
ACCENT_WIDTH = 40
SUBTITLE = "AI DevOps Daily"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / "thumbnail_log.txt"),
        ],
    )


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    max_width = x1 - x0
    avg_char_width = max(font.getlength("A"), 1)
    wrap_width = max(int(max_width / avg_char_width), 10)
    lines = textwrap.wrap(text, width=wrap_width)

    line_height = font.size + 12
    total_height = len(lines) * line_height
    start_y = y0 + max((y1 - y0 - total_height) // 2, 0)

    for index, line in enumerate(lines):
        line_width = font.getlength(line)
        x = x0 + (max_width - line_width) // 2
        y = start_y + index * line_height
        draw.text((x, y), line, font=font, fill=fill)


def generate_thumbnail(video_number: int) -> str:
    script_file = script_path(video_number)
    if not script_file.exists():
        raise FileNotFoundError(f"Script not found: {script_file}")

    content = script_file.read_text(encoding="utf-8")
    header = parse_header(content)
    title = header.get("title") or f"AI DevOps Daily #{video_number}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"thumbnail_{video_number}.jpg"

    logging.info("Generating thumbnail for video %s", video_number)
    logging.info("Title: %s", title)

    image = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(image)

    draw.rectangle([(0, 0), (ACCENT_WIDTH, HEIGHT)], fill=ACCENT_COLOR)

    title_font = find_font(64, bold=True)
    subtitle_font = find_font(32, bold=False)

    draw_wrapped_text(
        draw,
        title,
        title_font,
        (ACCENT_WIDTH + 60, 120, WIDTH - 60, HEIGHT - 120),
        (255, 255, 255),
    )

    subtitle_width = subtitle_font.getlength(SUBTITLE)
    draw.text(
        ((WIDTH - subtitle_width) // 2, HEIGHT - 70),
        SUBTITLE,
        font=subtitle_font,
        fill=(156, 163, 175),
    )

    logo_path = ASSETS_DIR / "logo.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
        image.paste(logo, (WIDTH - logo.width - 30, 30), logo)
        logging.info("Applied logo from %s", logo_path)
    else:
        logging.info("Logo not found at %s — skipping", logo_path)

    image.save(output_file, format="JPEG", quality=92)

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"Thumbnail generation failed: {output_file}")

    logging.info("Thumbnail saved successfully (%d bytes)", output_file.stat().st_size)
    return str(output_file)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Generate YouTube thumbnail")
    parser.add_argument("video_number", type=int, help="Video number (e.g. 1)")
    args = parser.parse_args()

    try:
        generate_thumbnail(args.video_number)
        return 0
    except Exception as exc:
        logging.exception("Thumbnail generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
