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

The workflow runs automatically every **Monday and Thursday at 10:00 AM EST** (15:00 UTC), or manually via **workflow_dispatch**. It processes the next video, uploads to YouTube, and commits the updated `tracker.json`.

## Requirements

- Python 3.11+
- FFmpeg (required by MoviePy)
- Google OAuth credentials for YouTube upload
