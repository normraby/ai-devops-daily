#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f client_secret.json ]]; then
  echo "Missing client_secret.json. Download OAuth credentials from Google Cloud Console first." >&2
  exit 1
fi

echo "Re-authorizing Google OAuth for YouTube upload + Gmail send."
echo "Sign in as the Google account that owns the YouTube channel (inraby@gmail.com)."
echo

python authorize_google.py

echo
echo "Updating GitHub secrets..."
gh secret set TOKEN_JSON < token.json
echo "Done. Re-run the daily status workflow to verify email delivery."
