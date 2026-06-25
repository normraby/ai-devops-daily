"""Shared Google OAuth credentials for YouTube upload and Gmail status emails."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parent
CLIENT_SECRET_FILE = PROJECT_ROOT / "client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"
EMAIL_TOKEN_FILE = PROJECT_ROOT / "token_email.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

EMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def has_gmail_scope(creds: Credentials) -> bool:
    scopes = set(creds.scopes or [])
    return "https://www.googleapis.com/auth/gmail.send" in scopes


def _load_token_file(
    token_file: Path,
    default_scopes: list[str],
    *,
    allow_interactive: bool,
) -> Credentials:
    creds = None
    scopes = list(default_scopes)
    if token_file.exists():
        token_data = json.loads(token_file.read_text(encoding="utf-8"))
        if token_data.get("scopes"):
            scopes = token_data["scopes"]
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired Google OAuth token (%s)", token_file.name)
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        elif allow_interactive:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CLIENT_SECRET_FILE}. Download OAuth credentials from Google Cloud Console."
                )
            logging.info("Starting OAuth flow — complete authentication in your browser")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), default_scopes)
            creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
            logging.info("Saved OAuth token to %s", token_file)
        else:
            raise EnvironmentError(
                f"Missing or expired OAuth token at {token_file}. "
                "Run: python authorize_google.py --email-only (sign in as inraby@gmail.com)"
            )

    return creds


def load_credentials() -> Credentials:
    return _load_token_file(TOKEN_FILE, SCOPES, allow_interactive=True)


def load_email_credentials() -> Credentials:
    return _load_token_file(EMAIL_TOKEN_FILE, EMAIL_SCOPES, allow_interactive=False)
