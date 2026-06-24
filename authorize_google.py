#!/usr/bin/env python3
"""Re-authorize Google OAuth with YouTube + Gmail send scopes."""

from __future__ import annotations

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from google_auth import CLIENT_SECRET_FILE, SCOPES, TOKEN_FILE

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    print("Re-authorizing Google OAuth with scopes:")
    for scope in SCOPES:
        print(f"  - {scope}")
    print()
    print("Enable Gmail API if prompted:")
    print("  https://console.cloud.google.com/apis/library/gmail.googleapis.com")
    print()

    if not CLIENT_SECRET_FILE.exists():
        print(f"ERROR: Missing {CLIENT_SECRET_FILE}", file=sys.stderr)
        return 1

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print(f"Removed old {TOKEN_FILE.name} to request updated scopes.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    print(f"\nSuccess. Token saved to {TOKEN_FILE}")
    print("Scopes granted:", ", ".join(creds.scopes or []))
    print("\nUpdate GitHub secret:")
    print("  gh secret set TOKEN_JSON < token.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
