#!/usr/bin/env python3
"""Re-authorize Google OAuth for YouTube uploads and/or Gmail status emails."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from google_auth import (
    CLIENT_SECRET_FILE,
    EMAIL_SCOPES,
    EMAIL_TOKEN_FILE,
    SCOPES,
    TOKEN_FILE,
)

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize Google OAuth for this project")
    parser.add_argument(
        "--email-only",
        action="store_true",
        help="Authorize Gmail send only (saves token_email.json; keeps token.json for YouTube)",
    )
    args = parser.parse_args()

    if args.email_only:
        scopes = EMAIL_SCOPES
        token_file = EMAIL_TOKEN_FILE
        account_hint = "inraby@gmail.com"
        secret_name = "EMAIL_TOKEN_JSON"
    else:
        scopes = SCOPES
        token_file = TOKEN_FILE
        account_hint = "norm@uaisystems.com (YouTube channel owner)"
        secret_name = "TOKEN_JSON"

    print("Re-authorizing Google OAuth with scopes:")
    for scope in scopes:
        print(f"  - {scope}")
    print()
    print(f"Sign in as: {account_hint}")
    print()
    print("Before authorizing, confirm in Google Cloud Console:")
    print("  OAuth consent screen scopes include the scopes above")
    print(f"  Test users include {account_hint}")
    print()
    print("Enable Gmail API if prompted:")
    print("  https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=ai-devops-daily")
    print()

    if not CLIENT_SECRET_FILE.exists():
        print(f"ERROR: Missing {CLIENT_SECRET_FILE}", file=sys.stderr)
        return 1

    if token_file.exists():
        token_file.unlink()
        print(f"Removed old {token_file.name} to request updated scopes.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), scopes)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_file.write_text(creds.to_json(), encoding="utf-8")

    print(f"\nSuccess. Token saved to {token_file}")
    print("Scopes granted:", ", ".join(creds.scopes or []))
    print("\nUpdate GitHub secret:")
    print(f"  gh secret set {secret_name} < {token_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
