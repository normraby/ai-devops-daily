#!/usr/bin/env python3
"""Update AI DevOps Daily YouTube channel About/description."""

from __future__ import annotations

import logging
import sys

from googleapiclient.discovery import build

from google_auth import load_credentials

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

ABOUT = """AI DevOps Daily — educational content on platform engineering, CI/CD, cloud cost, security, and AI automation for DevOps teams.

Production: AI-assisted scripting, text-to-speech narration, and original programmatic slide visuals with authored code examples. Metrics and scenarios are illustrative teaching examples unless a source is cited.

@AIDevOpsDaily-w8i

We are not affiliated with vendors mentioned. Not financial, legal, or professional advice.
"""


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])


def main() -> int:
    setup_logging()
    youtube = build("youtube", "v3", credentials=load_credentials())
    response = youtube.channels().list(part="brandingSettings", mine=True).execute()
    items = response.get("items", [])
    if not items:
        logging.error("No channel found")
        return 1

    channel_id = items[0]["id"]
    branding = items[0].get("brandingSettings", {}).get("channel", {})
    branding["description"] = ABOUT.strip()

    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel_id, "brandingSettings": {"channel": branding}},
    ).execute()
    logging.info("Updated channel description for %s", channel_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
