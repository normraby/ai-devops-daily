#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f client_secret.json ]]; then
  echo "Missing client_secret.json. Download OAuth credentials from Google Cloud Console first." >&2
  exit 1
fi

echo "Authorize Gmail send for daily status emails."
echo "Sign in as inraby@gmail.com (personal Gmail with a mailbox)."
echo "This does NOT change token.json used for YouTube uploads (norm@uaisystems.com)."
echo

python authorize_google.py --email-only

echo
echo "Updating GitHub secret EMAIL_TOKEN_JSON..."
gh secret set EMAIL_TOKEN_JSON < token_email.json
echo "Done. Re-run the daily status workflow to verify email delivery."
