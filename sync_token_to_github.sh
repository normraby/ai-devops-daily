#!/usr/bin/env bash
# Push refreshed token.json to GitHub Actions after local OAuth — run once after authorize_google.py
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f token.json ]]; then
  echo "ERROR: token.json missing. Run: .venv/bin/python authorize_google.py"
  exit 1
fi
gh secret set TOKEN_JSON --repo normraby/ai-devops-daily < token.json
echo "Updated TOKEN_JSON secret on normraby/ai-devops-daily"
