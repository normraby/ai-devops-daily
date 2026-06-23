# AI DevOps Daily

Automated YouTube content pipeline for the **AI DevOps Daily** channel. Generates voiceovers, videos, thumbnails, and uploads to YouTube on a schedule.

## Project Structure

```
ai-devops-daily/
├── video_scripts/     # 20 episode scripts (video_1.txt … video_20.txt)
├── assets/            # logo.png (optional watermark)
├── output/            # Generated MP3, MP4, JPG (gitignored)
├── logs/              # Pipeline and upload logs (gitignored)
├── generate_voiceover.py
├── generate_video.py
├── generate_thumbnail.py
├── upload_to_youtube.py
├── run_pipeline.py
├── tracker.json       # Tracks last uploaded video number
└── .github/workflows/upload.yml
```

## Quick Start

```bash
cd /Users/normandraby/dev/ai-devops-daily
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the full pipeline (processes next video from tracker.json)
python run_pipeline.py

# Or run individual steps
python generate_voiceover.py 1
python generate_video.py 1
python generate_thumbnail.py 1
python upload_to_youtube.py 1
```

## YouTube OAuth Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **YouTube Data API v3**
3. Create OAuth 2.0 credentials (Desktop app) and download as `client_secret.json`
4. Run `python upload_to_youtube.py 1` locally once to authenticate
5. Copy the contents of `token.json` to the GitHub secret `TOKEN_JSON`
6. Copy the contents of `client_secret.json` to the GitHub secret `CLIENT_SECRET_JSON`

## GitHub Actions

Two workflows run unattended on GitHub:

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `upload.yml` | Mon & Thu 10:00 AM EST | Full pipeline → YouTube upload → tracker commit |
| `daily-status.yml` | Daily 8:00 AM EST | Summary email of upload progress |

After each upload run, a **pipeline status email** is sent (success or failure). The daily workflow sends a progress summary even when no upload is scheduled.

### GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `CLIENT_SECRET_JSON` | YouTube OAuth client credentials |
| `TOKEN_JSON` | YouTube OAuth refresh token |
| `PEXELS_API_KEY` | Pexels stock footage API |
| `SMTP_PASSWORD` | Gmail [App Password](https://myaccount.google.com/apppasswords) for status emails |

Status emails go to **inraby@gmail.com** by default (configured in the workflow).

Manual run: **Actions → AI DevOps Daily Upload → Run workflow** (optional video number override).

## Requirements

- Python 3.11+
- FFmpeg (video generation; installed automatically in CI)
- Google OAuth credentials for YouTube upload
- Gmail App Password for status emails (optional locally via `.env`)
