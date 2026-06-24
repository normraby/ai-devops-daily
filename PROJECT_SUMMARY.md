# AI DevOps Daily — Project Summary

> Share this file with ChatGPT (or any advisor) for context on what exists and what to build next.

## What this is

**AI DevOps Daily** is a fully automated YouTube content pipeline for a DevOps/platform-engineering education channel. It generates voiceovers, renders original slide-based videos, creates thumbnails, uploads to YouTube, and runs on a schedule via GitHub Actions — with optional email status reports.

| Item | Value |
|------|-------|
| **GitHub repo** | https://github.com/normraby/ai-devops-daily |
| **YouTube channel** | https://www.youtube.com/@AIDevOpsDaily-w8i |
| **Local path** | `/Users/normandraby/dev/ai-devops-daily` |
| **Content plan** | 20 pre-written episode scripts (`video_scripts/video_1.txt` … `video_20.txt`) |
| **Upload cadence** | Mon & Thu 10:00 AM EST (GitHub Actions cron) |
| **Status email** | Daily summary + post-upload report → `inraby@gmail.com` |

---

## Pipeline architecture

```
video_scripts/video_N.txt
        │
        ▼
generate_voiceover.py   →  output/video_N.mp3     (edge-tts)
        │
        ▼
generate_video.py       →  output/video_N.mp4     (Pillow + matplotlib + ffmpeg)
        │
        ▼
generate_thumbnail.py   →  output/thumbnail_N.jpg (Pillow)
        │
        ▼
upload_to_youtube.py    →  YouTube (OAuth2 API)
        │
        ▼
tracker.json            →  committed by CI after successful upload
```

**Orchestrator:** `run_pipeline.py` — runs all steps, writes `logs/last_run_status.json` for email reports.

**Manual override:** `python run_pipeline.py --video N`

**Regenerate/re-upload:** `python regenerate_video.py N` (for replacing zero-view uploads)

---

## Video generation (current approach)

**No stock footage. No scraped docs.** All visuals are originally generated.

Each script segment has this structure:

```
0:00-0:30 - Section Title
Visual: [what to show — diagrams, charts, code, etc.]
Voiceover: [narration text]
```

The renderer parses `Visual:` + `Voiceover:` blocks and produces slides:

| Slide type | Source |
|------------|--------|
| Flow / architecture diagrams | Arrow chains from Visual line |
| Bar / line charts | Numbers from narration (labeled illustrative) |
| Code examples | Original teaching snippets in `slide_content.py` (YAML, HCL, Groovy, etc.) |
| Key takeaways | Extracted from voiceover bullets |
| Reference links | Official doc URLs as text only (no screenshots) |
| Comparison tables, timelines, cards | Parsed from Visual direction |

**Key files:**
- `visual_slides.py` — slide renderer
- `slide_content.py` — code snippets, takeaways, compliance text, reference links
- `script_utils.py` — parses script headers and segments

Every slide includes a compliance footer. YouTube descriptions get an educational disclaimer appended automatically.

---

## GitHub Actions workflows

| Workflow | File | Schedule | Purpose |
|----------|------|----------|---------|
| Upload | `.github/workflows/upload.yml` | Mon/Thu 15:00 UTC | Full pipeline → upload → commit `tracker.json` → email |
| Daily status | `.github/workflows/daily-status.yml` | Daily 13:00 UTC | Progress summary email |

**CI environment:** Ubuntu, Python 3.11, ffmpeg, DejaVu fonts. Video gen uses ffmpeg `zoompan` (no MoviePy — removed due to OOM on GitHub runners).

---

## GitHub secrets required

| Secret | Purpose |
|--------|---------|
| `CLIENT_SECRET_JSON` | YouTube OAuth client credentials |
| `TOKEN_JSON` | YouTube OAuth refresh token |
| `SMTP_PASSWORD` | Gmail App Password for status emails |

`PEXELS_API_KEY` is **no longer used** (stock footage removed).

---

## Upload tracker (as of last update)

| # | Title (short) | YouTube URL | Notes |
|---|---------------|-------------|-------|
| 1 | Why Jenkins is Dying | https://www.youtube.com/watch?v=isvLkmuKe48 | Old stock-footage style · has views · **not regenerated** |
| 2 | (episode 2) | https://www.youtube.com/watch?v=eWK2we6wdxc | Old style · has views · **not regenerated** |
| 3 | (episode 3) | https://www.youtube.com/watch?v=AbzKHaTCjW4 | Old style · has views · **not regenerated** |
| 4 | Kubernetes Cost Optimization | https://www.youtube.com/watch?v=-JpiKxSF9Qs | **Regenerated** with new slide format (replaced `ri5aPyLn5WI`) |
| 5 | GitOps | https://www.youtube.com/watch?v=KaRwO_DiZG4 | **Regenerated** with new slide format (replaced `mJTbgB83Db8`) |
| 6–20 | Scripts written | Not uploaded yet | Next auto-upload: **video 6** |

**Orphan videos to delete manually in YouTube Studio** (OAuth lacks delete scope):
- https://www.youtube.com/watch?v=ri5aPyLn5WI (old video 4)
- https://www.youtube.com/watch?v=mJTbgB83Db8 (old video 5)

---

## Email notifications

`send_status_email.py` — two modes:
- `--mode pipeline` — after each upload run (success/failure + log tail)
- `--mode daily` — channel progress summary

Requires `SMTP_PASSWORD` GitHub secret (Gmail App Password). Email step uses `continue-on-error: true` so missing SMTP doesn't fail the pipeline.

---

## Local development

```bash
cd /Users/normandraby/dev/ai-devops-daily
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full pipeline (next video from tracker)
python run_pipeline.py

# Individual steps
python generate_voiceover.py 6
python generate_video.py 6
python generate_thumbnail.py 6
python upload_to_youtube.py 6

# Regenerate a zero-view upload
python regenerate_video.py 6
```

**Requirements:** Python 3.11+, ffmpeg, YouTube OAuth files (`client_secret.json`, `token.json`) for local upload.

---

## Content & legal design choices

- All visuals generated in-code (Pillow + matplotlib + ffmpeg)
- Code examples are original minimal teaching snippets, not copied from vendor docs
- Charts labeled as illustrative / aligned with narration — not third-party survey data
- Case studies marked as hypothetical learning scenarios
- Vendor names used in educational context only (no logos)
- No scraped screenshots or copyrighted assets

---

## Known limitations & open items

1. **OAuth scope** — token has `youtube.upload` only. Cannot read view counts or delete videos via API. Delete orphans manually in YouTube Studio. Re-auth with broader scope if automation needed.

2. **SMTP** — `SMTP_PASSWORD` secret may still need to be set for emails to work.

3. **Videos 1–3** — still old Pexels/stock-footage style (kept because they had views). Could regenerate later if desired.

4. **Logo** — `assets/logo.png` missing; thumbnails/closing slides skip logo.

5. **Slide quality** — functional but basic. Room for: Mermaid diagrams, better chart data extraction, real doc screenshots (with permission), animated transitions, chapter markers.

6. **YouTube metadata** — no chapter timestamps, pinned comments, or playlists automated yet.

7. **Analytics loop** — no feedback from YouTube Analytics into content decisions.

8. **Token maintenance** — OAuth token expires; CI secret must be refreshed after local re-auth.

---

## Suggested areas for ChatGPT to advise on

- **Content strategy:** Which topics from scripts 6–20 to prioritize; SEO titles/tags; series playlists
- **Quality upgrades:** Slide design, diagram fidelity, chapter markers, Shorts clips from long-form
- **Growth:** Thumbnail A/B testing, publish time optimization, community posts
- **Ops:** OAuth scope expansion, automated orphan cleanup, monitoring/alerting beyond email
- **Monetization/compliance:** YouTube Partner Program readiness, disclosure requirements for AI-generated content
- **Regenerating videos 1–3** once views plateau — workflow and SEO impact of replacing URLs

---

## File map (essential)

```
ai-devops-daily/
├── video_scripts/          # 20 episode scripts
├── generate_voiceover.py
├── generate_video.py
├── generate_thumbnail.py
├── upload_to_youtube.py
├── run_pipeline.py
├── regenerate_video.py
├── send_status_email.py
├── visual_slides.py        # slide renderer
├── slide_content.py        # code snippets, takeaways, compliance
├── script_utils.py
├── tracker.json
├── .github/workflows/
│   ├── upload.yml
│   └── daily-status.yml
├── README.md
└── PROJECT_SUMMARY.md      # this file
```

---

*Last updated: June 2026 · 5 of 20 videos live · slide-based renderer in production*
