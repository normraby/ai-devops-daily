#!/usr/bin/env python3
"""Generate MP3 voiceover from video script using edge-tts."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import edge_tts

from pathlib import Path

from script_utils import OUTPUT_DIR, extract_voiceover_text, script_path

PROJECT_ROOT = Path(__file__).resolve().parent

VOICE = "en-US-GuyNeural"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / "voiceover_log.txt"),
        ],
    )


async def synthesize(text: str, output_file: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)


def generate_voiceover(video_number: int) -> str:
    path = script_path(video_number)
    if not path.exists():
        raise FileNotFoundError(f"Script not found: {path}")

    content = path.read_text(encoding="utf-8")
    voiceover_text = extract_voiceover_text(content)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"video_{video_number}.mp3"

    logging.info("Generating voiceover for video %s", video_number)
    logging.info("Voice: %s", VOICE)
    logging.info("Output: %s", output_file)
    logging.info("Voiceover length: %d characters", len(voiceover_text))

    asyncio.run(synthesize(voiceover_text, str(output_file)))

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(f"Voiceover generation failed: {output_file}")

    logging.info("Voiceover saved successfully (%d bytes)", output_file.stat().st_size)
    return str(output_file)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Generate voiceover MP3 from script")
    parser.add_argument("video_number", type=int, help="Video number (e.g. 1)")
    args = parser.parse_args()

    try:
        generate_voiceover(args.video_number)
        return 0
    except Exception as exc:
        logging.exception("Voiceover generation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
