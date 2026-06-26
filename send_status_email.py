#!/usr/bin/env python3
"""Send pipeline and daily status emails via OAuth SMTP, app password, or Gmail API."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import smtplib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_auth import EMAIL_TOKEN_FILE, TOKEN_FILE, has_gmail_scope, load_credentials, load_email_credentials
from script_utils import LOGS_DIR, parse_header, script_path

PROJECT_ROOT = Path(__file__).resolve().parent
TRACKER_FILE = PROJECT_ROOT / "tracker.json"
STATUS_FILE = LOGS_DIR / "last_run_status.json"
PIPELINE_LOG = LOGS_DIR / "pipeline_log.txt"

DEFAULT_TO = "inraby@gmail.com"
DEFAULT_FROM = "inraby@gmail.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
GMAIL_API_ENABLE_URL = (
    "https://console.cloud.google.com/apis/library/gmail.googleapis.com"
    "?project=ai-devops-daily"
)

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


def get_oauth_account_email(creds) -> str:
    """Resolve the Google account tied to the OAuth access token."""
    configured = os.getenv("OAUTH_SENDER_EMAIL", "").strip()
    if configured:
        return configured

    if not creds.token:
        raise EnvironmentError("OAuth access token missing after refresh")

    for url in (
        "https://www.googleapis.com/oauth2/v3/userinfo",
        "https://openidconnect.googleapis.com/v1/userinfo",
    ):
        try:
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode())
            email = payload.get("email", "").strip()
            if email:
                logging.info("Resolved OAuth sender email via userinfo")
                return email
        except Exception as exc:
            logging.debug("userinfo lookup failed for %s: %s", url, exc)

    url = f"https://oauth2.googleapis.com/tokeninfo?access_token={creds.token}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise EnvironmentError(f"Could not verify OAuth account: {exc}") from exc

    scopes = payload.get("scope", "")
    logging.info("OAuth token scopes: %s", scopes)
    email = payload.get("email", "").strip()
    if email:
        return email

    fallback = os.getenv("EMAIL_FROM", DEFAULT_FROM)
    logging.warning(
        "OAuth identity unknown; using configured sender %s. "
        "Run: python authorize_google.py (sign in as %s), then update TOKEN_JSON.",
        fallback,
        DEFAULT_TO,
    )
    return fallback


def encode_gmail_raw(subject: str, body_text: str, body_html: str | None, to: str, from_addr: str | None = None) -> str:
    """Build a RFC 2822 message and base64url-encode it for Gmail API."""
    message = EmailMessage()
    message["To"] = to
    if from_addr:
        message["From"] = from_addr
    message["Subject"] = subject
    if body_html:
        message.set_content(body_text, subtype="plain", charset="utf-8")
        message.add_alternative(body_html, subtype="html", charset="utf-8")
    else:
        message.set_content(body_text, charset="utf-8")
    return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")


def gmail_send_precondition_error(exc: HttpError, from_addr: str) -> EnvironmentError | None:
    if "failedPrecondition" not in str(exc) and "Precondition check failed" not in str(exc):
        return None
    if from_addr.endswith("@gmail.com"):
        hint = (
            f"  1. Re-run: python authorize_google.py (sign in as {from_addr})\n"
            "  2. Add gmail.send to OAuth consent screen scopes in Google Cloud Console\n"
            f"  3. Add {from_addr} as a test user on the OAuth consent screen"
        )
    else:
        hint = (
            f"The OAuth account ({from_addr}) does not have a Gmail mailbox "
            "(common for custom domains routed through non-Google email).\n"
            f"  1. Set SMTP_PASSWORD to a Gmail App Password for {DEFAULT_TO}\n"
            f"  2. Keep OAuth as {from_addr} for YouTube uploads; use SMTP for status email"
        )
    return EnvironmentError(
        "Gmail API rejected the send (precondition failed).\n" + hint
    )


def gmail_api_not_enabled_error(exc: HttpError) -> EnvironmentError | None:
    """Return a clearer error when Gmail API is disabled in Google Cloud."""
    try:
        details = exc.error_details if hasattr(exc, "error_details") else []
    except Exception:
        details = []
    for detail in details:
        if detail.get("reason") == "accessNotConfigured":
            return EnvironmentError(
                "Gmail API is not enabled for the ai-devops-daily Google Cloud project. "
                f"Enable it here, wait a minute, then retry: {GMAIL_API_ENABLE_URL}"
            )
    if "accessNotConfigured" in str(exc) or "Gmail API has not been used" in str(exc):
        return EnvironmentError(
            "Gmail API is not enabled for the ai-devops-daily Google Cloud project. "
            f"Enable it here, wait a minute, then retry: {GMAIL_API_ENABLE_URL}"
        )
    return None


def resolve_gmail_api_credentials():
    if EMAIL_TOKEN_FILE.exists():
        creds = load_email_credentials()
        if not has_gmail_scope(creds):
            raise EnvironmentError(
                "Email OAuth token missing gmail.send scope. Run: python authorize_google.py --email-only"
            )
        return creds

    if TOKEN_FILE.exists():
        creds = load_credentials()
        if has_gmail_scope(creds) and oauth_account_has_gmail_mailbox(creds):
            return creds

    raise EnvironmentError(
        "Missing token_email.json for Gmail API send. Run: ./setup_email_auth.sh "
        "(sign in as inraby@gmail.com)"
    )


def send_via_gmail_api(subject: str, body_text: str, body_html: str | None = None) -> None:
    creds = resolve_gmail_api_credentials()

    to = os.getenv("EMAIL_TO", DEFAULT_TO)
    from_addr = get_oauth_account_email(creds)
    raw = encode_gmail_raw(subject, body_text, body_html, to, from_addr)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    logging.info("Sending email via Gmail API from %s to %s: %s", from_addr, to, subject)
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as exc:
        configured = gmail_api_not_enabled_error(exc)
        if configured:
            raise configured from exc
        precondition = gmail_send_precondition_error(exc, from_addr)
        if precondition:
            raise precondition from exc
        raise


def smtp_password_from_env() -> str:
    return os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")


def smtp_xoauth2_string(username: str, access_token: str) -> str:
    auth_str = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth_str.encode()).decode()


def send_via_smtp_oauth(subject: str, body_text: str, body_html: str | None = None) -> None:
    """Send via Gmail SMTP using the same OAuth token as YouTube uploads."""
    if not TOKEN_FILE.exists():
        raise EnvironmentError(f"Missing {TOKEN_FILE} for OAuth SMTP send")

    creds = load_credentials()
    if not has_gmail_scope(creds):
        raise EnvironmentError(
            "OAuth token missing gmail.send scope. Run: python authorize_google.py"
        )
    if not creds.token:
        raise EnvironmentError("OAuth access token missing after refresh")

    load_dotenv(PROJECT_ROOT / ".env")
    to = os.getenv("EMAIL_TO", DEFAULT_TO)
    from_addr = get_oauth_account_email(creds)
    message = build_message(subject, body_text, body_html, to, from_addr)

    host = os.getenv("SMTP_HOST", DEFAULT_SMTP_HOST)
    port = int(os.getenv("SMTP_PORT", str(DEFAULT_SMTP_PORT)))

    logging.info("Sending email via OAuth SMTP from %s to %s: %s", from_addr, to, subject)
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        auth_b64 = smtp_xoauth2_string(from_addr, creds.token)
        code, response = server.docmd("AUTH", "XOAUTH2 " + auth_b64)
        if code != 235:
            raise smtplib.SMTPAuthenticationError(code, response)
        server.sendmail(from_addr, [to], message.as_string())


def send_via_smtp(subject: str, body_text: str, body_html: str | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    password = smtp_password_from_env()
    if not password:
        raise EnvironmentError(
            "SMTP_PASSWORD not set. Add a Gmail App Password to .env or the "
            "SMTP_PASSWORD GitHub secret, or enable Gmail API for OAuth send."
        )

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


def oauth_account_has_gmail_mailbox(creds) -> bool:
    """Gmail API/SMTP OAuth only work when the signed-in account uses Gmail for mail."""
    try:
        email = get_oauth_account_email(creds).lower()
    except Exception:
        return False
    return email.endswith("@gmail.com")


def send_email(subject: str, body_text: str, body_html: str | None = None) -> None:
    """Prefer Gmail API (token_email.json), then app-password SMTP."""
    load_dotenv(PROJECT_ROOT / ".env")
    smtp_password = smtp_password_from_env()
    errors: list[Exception] = []

    if EMAIL_TOKEN_FILE.exists():
        try:
            send_via_gmail_api(subject, body_text, body_html)
            return
        except Exception as exc:
            errors.append(exc)
            logging.warning("Gmail API send failed (%s)", exc)
    elif TOKEN_FILE.exists() and oauth_account_has_gmail_mailbox(load_credentials()):
        try:
            send_via_gmail_api(subject, body_text, body_html)
            return
        except Exception as exc:
            errors.append(exc)
            logging.warning("Gmail API send failed (%s)", exc)
    elif TOKEN_FILE.exists():
        try:
            sender = get_oauth_account_email(load_credentials())
        except Exception:
            sender = "OAuth account"
        logging.info(
            "No token_email.json and %s has no Gmail mailbox. Run ./setup_email_auth.sh.",
            sender,
        )

    if smtp_password:
        try:
            send_via_smtp(subject, body_text, body_html)
            return
        except Exception as exc:
            errors.append(exc)
            logging.warning("App-password SMTP send failed (%s)", exc)

    if errors:
        raise errors[-1]
    raise EnvironmentError(
        "Email not configured. Run: ./setup_email_auth.sh (sign in as inraby@gmail.com)"
    )


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
