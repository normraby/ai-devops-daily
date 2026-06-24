#!/usr/bin/env python3
"""Send pipeline and daily status emails via Gmail API or SMTP fallback."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

from google_auth import TOKEN_FILE, has_gmail_scope, load_credentials
from script_utils import LOGS_DIR, parse_header, script_path

PROJECT_ROOT = Path(__file__).resolve().parent
TRACKER_FILE = PROJECT_ROOT / "tracker.json"
STATUS_FILE = LOGS_DIR / "last_run_status.json"
PIPELINE_LOG = LOGS_DIR / "pipeline_log.txt"

DEFAULT_TO = "inraby@gmail.com"
DEFAULT_FROM = "inraby@gmail.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def build_message(subject: str, body_text: str, body_html: str | None, to: str, from_addr: str) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to
    message.attach(MIMEText(body_text, "plain"))
    if body_html:
        message.attach(MIMEText(body_html, "html"))
    return message


def send_via_gmail_api(subject: str, body_text: str, body_html: str | None = None) -> None:
    if not TOKEN_FILE.exists():
        raise EnvironmentError(f"Missing {TOKEN_FILE} for Gmail API send")

    creds = load_credentials()
    if not has_gmail_scope(creds):
        raise EnvironmentError(
            "OAuth token missing gmail.send scope. Run: python authorize_google.py"
        )

    to = os.getenv("EMAIL_TO", DEFAULT_TO)
    message = build_message(subject, body_text, body_html, to, DEFAULT_FROM)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    logging.info("Sending email via Gmail API to %s: %s", to, subject)
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def send_via_smtp(subject: str, body_text: str, body_html: str | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not password:
        raise EnvironmentError("SMTP_PASSWORD not set")

    to = os.getenv("EMAIL_TO", DEFAULT_TO)
    from_addr = os.getenv("EMAIL_FROM", os.getenv("SMTP_USERNAME", DEFAULT_FROM))
    message = build_message(subject, body_text, body_html, to, from_addr)

    host = os.getenv("SMTP_HOST", DEFAULT_SMTP_HOST)
    port = int(os.getenv("SMTP_PORT", str(DEFAULT_SMTP_PORT)))
    username = os.getenv("SMTP_USERNAME", DEFAULT_FROM)

    logging.info("Sending email via SMTP to %s: %s", to, subject)
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(from_addr, [to], message.as_string())


def send_email(subject: str, body_text: str, body_html: str | None = None) -> None:
    """Prefer Gmail API (uses TOKEN_JSON); fall back to SMTP if configured."""
    load_dotenv(PROJECT_ROOT / ".env")
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()

    if TOKEN_FILE.exists():
        try:
            send_via_gmail_api(subject, body_text, body_html)
            return
        except Exception as exc:
            if smtp_password:
                logging.warning("Gmail API send failed (%s); trying SMTP", exc)
            else:
                raise

    send_via_smtp(subject, body_text, body_html)


def load_tracker() -> dict:
    if not TRACKER_FILE.exists():
        return {"last_uploaded": 0, "videos": {}}
    return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))


def load_status() -> dict:
    if not STATUS_FILE.exists():
        return {}
    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))


def tail_log(lines: int = 40) -> str:
    if not PIPELINE_LOG.exists():
        return "(no pipeline log yet)"
    content = PIPELINE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def build_pipeline_report() -> tuple[str, str, str]:
    status = load_status()
    tracker = load_tracker()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    video_number = status.get("video_number", "?")
    run_status = status.get("status", "unknown")
    title = status.get("title", "Unknown")
    url = status.get("url", "")
    error = status.get("error", "")
    video_id = status.get("video_id", "")

    subject_prefix = "SUCCESS" if run_status == "uploaded" else "FAILED"
    subject = f"AI DevOps Daily — {subject_prefix} — Video {video_number}"

    text_lines = [
        "AI DevOps Daily Pipeline Report",
        f"Time: {now}",
        f"Status: {run_status}",
        f"Video: {video_number}",
        f"Title: {title}",
    ]
    if video_id:
        text_lines.append(f"YouTube ID: {video_id}")
    if url:
        text_lines.append(f"URL: {url}")
    if error:
        text_lines.append(f"Error: {error}")
    text_lines.extend([
        "",
        f"Tracker last_uploaded: {tracker.get('last_uploaded', 0)}",
        "",
        "Recent log:",
        tail_log(),
    ])
    body_text = "\n".join(text_lines)

    status_color = "#22c55e" if run_status == "uploaded" else "#ef4444"
    body_html = f"""
    <html><body style="font-family:Arial,sans-serif;line-height:1.5">
      <h2>AI DevOps Daily Pipeline Report</h2>
      <p><strong>Time:</strong> {now}</p>
      <p><strong>Status:</strong> <span style="color:{status_color}">{run_status}</span></p>
      <p><strong>Video:</strong> {video_number}</p>
      <p><strong>Title:</strong> {title}</p>
      {"<p><strong>YouTube:</strong> <a href='" + url + "'>" + url + "</a></p>" if url else ""}
      {"<p><strong>Error:</strong> " + error + "</p>" if error else ""}
      <p><strong>Tracker last_uploaded:</strong> {tracker.get("last_uploaded", 0)}</p>
      <pre style="background:#111;color:#eee;padding:12px;border-radius:8px">{tail_log()}</pre>
    </body></html>
    """
    return subject, body_text, body_html


def build_daily_summary() -> tuple[str, str, str]:
    tracker = load_tracker()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    last = int(tracker.get("last_uploaded", 0))
    next_video = last + 1 if last < 20 else None
    videos = tracker.get("videos", {})

    uploaded = [v for v in videos.values() if v.get("status") == "uploaded"]
    failed = [(k, v) for k, v in videos.items() if v.get("status") == "failed"]

    subject = f"AI DevOps Daily — Daily Status ({now[:10]})"

    text_lines = [
        "AI DevOps Daily — Daily Status",
        f"Time: {now}",
        f"Videos uploaded: {len(uploaded)} / 20",
        f"Last uploaded: {last}",
        f"Next scheduled video: {next_video if next_video else 'Complete'}",
        "",
        "Recent uploads:",
    ]
    for num in sorted(videos.keys(), key=lambda x: int(x)):
        entry = videos[num]
        if entry.get("status") == "uploaded":
            text_lines.append(f"  Video {num}: {entry.get('url', entry.get('video_id', 'uploaded'))}")
    if failed:
        text_lines.append("")
        text_lines.append("Failures:")
        for num, entry in failed:
            text_lines.append(f"  Video {num}: {entry.get('error', 'failed')}")

    if next_video and next_video <= 20:
        try:
            header = parse_header(script_path(next_video).read_text(encoding="utf-8"))
            text_lines.extend(["", f"Up next — Video {next_video}: {header.get('title', '')}"])
        except OSError:
            pass

    body_text = "\n".join(text_lines)
    body_html = (
        "<html><body style='font-family:Arial,sans-serif'>"
        f"<h2>AI DevOps Daily — Daily Status</h2>"
        f"<p><strong>Time:</strong> {now}</p>"
        f"<p><strong>Videos uploaded:</strong> {len(uploaded)} / 20</p>"
        f"<p><strong>Last uploaded:</strong> {last}</p>"
        f"<p><strong>Next video:</strong> {next_video if next_video else 'Complete'}</p>"
        "<ul>"
        + "".join(
            f"<li>Video {num}: {entry.get('url', 'uploaded')}</li>"
            for num, entry in sorted(videos.items(), key=lambda x: int(x[0]))
            if entry.get("status") == "uploaded"
        )
        + "</ul></body></html>"
    )
    return subject, body_text, body_html


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Send AI DevOps Daily status email")
    parser.add_argument(
        "--mode",
        choices=["pipeline", "daily"],
        default="pipeline",
        help="pipeline = after upload run, daily = daily summary",
    )
    args = parser.parse_args()

    try:
        if args.mode == "daily":
            subject, text, html = build_daily_summary()
        else:
            subject, text, html = build_pipeline_report()
        send_email(subject, text, html)
        logging.info("Email sent successfully")
        return 0
    except Exception as exc:
        logging.exception("Failed to send email: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
