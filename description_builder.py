"""Build YouTube descriptions with chapters, references, and compliance blocks."""

from __future__ import annotations

from reference_links import references_for_video
from script_utils import parse_segments

CHANNEL_NAME = "AI DevOps Daily"
CHANNEL_HANDLE = "@AIDevOpsDaily-w8i"

AI_DISCLOSURE = (
    "Production note: AI-assisted scripting, text-to-speech narration, and programmatic "
    "slide visuals. Code examples are original teaching snippets. Metrics and scenarios "
    "are illustrative unless a public source is cited below."
)

COMPLIANCE_FOOTER = (
    "Original educational content by AI DevOps Daily. We are not affiliated with vendors "
    "mentioned. Not financial, legal, or professional advice."
)


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(max(0, int(seconds)), 60)
    return f"{minutes}:{secs:02d}"


def build_chapters(content: str) -> str:
    segments = parse_segments(content)
    if not segments:
        return ""
    lines = ["Chapters:"]
    for segment in segments:
        lines.append(f"{format_timestamp(segment['start'])} {segment['title']}")
    return "\n".join(lines)


def build_references_block(video_number: int) -> str:
    refs = references_for_video(video_number)
    if not refs:
        return ""
    lines = ["Reference links (official docs, educational use):"]
    for label, url in refs:
        lines.append(f"• {label}: {url}")
    return "\n".join(lines)


def build_pinned_comment(video_number: int, title: str) -> str:
    return (
        f"🛠 {title}\n\n"
        "Educational DevOps content — illustrative scenarios unless cited. "
        "Not affiliated with vendors mentioned.\n\n"
        f"Subscribe → {CHANNEL_HANDLE}"
    )


def build_description(video_number: int, content: str, header: dict[str, str]) -> str:
    intro = header.get("description") or "AI DevOps Daily — platform engineering and AI automation insights."
    sections = [
        intro.strip(),
        build_chapters(content),
        build_references_block(video_number),
        AI_DISCLOSURE,
        _playlist_hint(video_number),
        f"---\n{COMPLIANCE_FOOTER}",
    ]
    return "\n\n".join(block for block in sections if block.strip())


def _playlist_hint(video_number: int) -> str:
    if video_number <= 5:
        return "Suggested playlist: CI/CD & Platform Engineering"
    if video_number <= 10:
        return "Suggested playlist: Cloud Cost & Security"
    if video_number <= 15:
        return "Suggested playlist: GitOps & Kubernetes"
    return "Suggested playlist: AI Agents & SRE"
