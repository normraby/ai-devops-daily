"""Render documentation-style slides from script Visual: directions."""

from __future__ import annotations

import io
import re
import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

from slide_content import (
    CASE_STUDY_NOTE,
    CHART_DISCLAIMER,
    COMPLIANCE_FOOTER,
    build_segment_context,
    extract_key_terms,
    extract_takeaways,
    wants_code_slide,
)

WIDTH, HEIGHT = 1920, 1080
FOOTER_HEIGHT = 44
TAKEAWAY_PANEL_TOP = HEIGHT - 280
BG = (13, 17, 23)
ACCENT = (255, 0, 0)
TEXT = (255, 255, 255)
MUTED = (156, 163, 175)
PANEL = (22, 27, 34)
BORDER = (48, 54, 61)
GREEN = (34, 197, 94)
BLUE = (59, 130, 246)
YELLOW = (234, 179, 8)
BRAND = "AI DevOps Daily"

ARROW_SPLIT = re.compile(r"\s*(?:→|->|—>)\s*")
NUMBERED = re.compile(r"^\d+\.\s*")
YEAR_VALUE = re.compile(r"(\d{4}).*?(\d+(?:\.\d+)?)\s*%", re.I)
PCT_PAIR = re.compile(
    r"from\s+(\d+(?:\.\d+)?)\s*%\s+to\s+(\d+(?:\.\d+)?)\s*%|"
    r"(\d+(?:\.\d+)?)\s*%\s+to\s+(\d+(?:\.\d+)?)\s*%",
    re.I,
)
METRIC = re.compile(
    r"(\d+(?:\.\d+)?)\s*x|(\d+(?:\.\d+)?)\s*%|down\s+(\d+(?:\.\d+)?)\s*%",
    re.I,
)


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    from pathlib import Path

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def new_slide() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0, 0), (8, HEIGHT)], fill=ACCENT)
    return image, draw


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str = BRAND) -> int:
    title_font = find_font(42, bold=True)
    sub_font = find_font(22)
    y = 48
    draw.text((48, y), title, font=title_font, fill=TEXT)
    y += 56
    draw.text((48, y), subtitle, font=sub_font, fill=MUTED)
    draw.line([(48, y + 36), (WIDTH - 48, y + 36)], fill=BORDER, width=2)
    return y + 56


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    avg = max(font.getlength("A"), 8)
    width_chars = max(int(max_width / avg), 12)
    lines: list[str] = []
    for paragraph in text.split(". "):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        wrapped = textwrap.wrap(paragraph, width=width_chars)
        lines.extend(wrapped)
    return lines[:12]


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int] = TEXT,
) -> None:
    x0, y0, x1, y1 = box
    lines = wrap_text(text, font, x1 - x0)
    line_h = font.size + 10
    for index, line in enumerate(lines):
        y = y0 + index * line_h
        if y + line_h > y1:
            break
        draw.text((x0, y), line, font=font, fill=fill)


def draw_compliance_footer(draw: ImageDraw.ImageDraw, extra: str = "") -> None:
    text = COMPLIANCE_FOOTER
    if extra:
        text = f"{extra} · {COMPLIANCE_FOOTER}"
    draw.text((48, HEIGHT - 32), text[:200], font=find_font(15), fill=MUTED)


def draw_takeaways_panel(
    draw: ImageDraw.ImageDraw,
    takeaways: list[str],
    y_start: int | None = None,
) -> None:
    if not takeaways:
        return
    y0 = y_start if y_start is not None else TAKEAWAY_PANEL_TOP
    draw.text((48, y0), "Key takeaways", font=find_font(22, bold=True), fill=YELLOW)
    body = find_font(19)
    y = y0 + 34
    for item in takeaways[:3]:
        line = textwrap.shorten(item, width=110, placeholder="…")
        draw.text((48, y), f"▸ {line}", font=body, fill=TEXT)
        y += 30


def draw_references_panel(draw: ImageDraw.ImageDraw, references: list[str], y: int) -> None:
    if not references:
        return
    draw.text((48, y), "Learn more (official docs)", font=find_font(18, bold=True), fill=BLUE)
    mono = find_font(17)
    for index, link in enumerate(references[:2]):
        draw.text((48, y + 28 + index * 26), f"• {link}", font=mono, fill=MUTED)


def draw_code_panel(
    draw: ImageDraw.ImageDraw,
    snippet: dict[str, str],
    box: tuple[int, int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    draw_rounded_rect(draw, (x0, y0, x1, y1), (10, 14, 20))
    draw.rectangle([(x0, y0), (x1, y0 + 44)], fill=(30, 35, 42))
    draw.text((x0 + 16, y0 + 10), snippet.get("title", "Example"), font=find_font(20, bold=True), fill=GREEN)
    draw.text((x0 + x1 - x0 - 80, y0 + 12), snippet.get("lang", "code"), font=find_font(16), fill=MUTED)
    mono = find_font(18)
    mono_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
    if mono_path.exists():
        mono = ImageFont.truetype(str(mono_path), 18)
    lines = snippet.get("body", "").splitlines()
    cy = y0 + 56
    for line in lines[:16]:
        if cy + 24 > y1:
            break
        color = GREEN if line.strip().startswith("#") else TEXT
        draw.text((x0 + 16, cy), line[:90], font=mono, fill=color)
        cy += 24


def classify_visual(visual: str, title: str) -> str:
    combined = f"{visual} {title}".lower()
    if any(w in combined for w in ["logo", "subscribe", "closing", "tagline"]):
        return "closing"
    if wants_code_slide(visual, title):
        return "code"
    if any(w in combined for w in ["chart", "graph", "bar chart", "trend line", "infographic", "metrics"]):
        return "chart"
    if "timeline" in combined or "minute-by-minute" in combined or "roadmap" in combined:
        return "timeline"
    if "comparison table" in combined or ("table" in combined and " vs " in combined):
        return "table"
    if any(w in combined for w in ["side-by-side", " vs ", "compare", "comparison"]):
        return "comparison"
    if any(w in combined for w in ["tree", "structure", "monorepo", "directory"]):
        return "tree"
    if any(w in combined for w in ["checklist", "numbered", "cards", "principle", "pitfall", "warning", "matrix"]):
        return "cards"
    if "case study" in combined:
        return "case_study"
    if any(w in combined for w in ["screenshot", "documentation", "plugin"]):
        return "doc"
    if any(w in combined for w in ["diagram", "flow", "architecture", "loop", "layer"]):
        return "flow"
    return "generic"


def parse_flow_nodes(visual: str) -> list[str]:
    if "→" in visual or "->" in visual or "—>" in visual:
        parts = ARROW_SPLIT.split(visual)
        nodes = []
        for part in parts:
            cleaned = re.sub(r"^(visual:|diagram:|flow:)\s*", "", part, flags=re.I).strip()
            cleaned = re.sub(r"\.\s*.*$", "", cleaned).strip()
            if cleaned and len(cleaned) < 80:
                nodes.append(cleaned)
        return nodes[:8]
    return []


def parse_list_items(visual: str) -> list[str]:
    items: list[str] = []
    for chunk in re.split(r"[.;]\s+", visual):
        chunk = chunk.strip()
        if not chunk:
            continue
        chunk = NUMBERED.sub("", chunk)
        if chunk.lower().startswith("visual:"):
            chunk = chunk.split(":", 1)[1].strip()
        if len(chunk) > 4:
            items.append(chunk)
    if len(items) == 1 and "," in items[0]:
        items = [part.strip() for part in items[0].split(",") if part.strip()]
    return items[:6]


def parse_comparison_columns(visual: str) -> tuple[str, str, list[str], list[str]]:
    left_title, right_title = "Traditional", "Modern"
    left_items: list[str] = []
    right_items: list[str] = []

    if ". " in visual and "compare" in visual.lower():
        parts = visual.split(". Compare", 1)
        if len(parts) == 2:
            left_part, right_part = parts[0], "Compare" + parts[1]
        else:
            left_part, right_part = visual, ""
    elif ". " in visual and " vs " not in visual.lower():
        split = visual.split(". ", 1)
        left_part = split[0]
        right_part = split[1] if len(split) > 1 else ""
    else:
        left_part = visual
        right_part = ""

    for side, items, default_title in [
        (left_part, left_items, left_title),
        (right_part, right_items, right_title),
    ]:
        if not side:
            continue
        if ":" in side:
            label, body = side.split(":", 1)
            if side is left_part:
                left_title = label.strip()[:40]
            else:
                right_title = label.strip()[:40]
            side = body
        arrow_parts = parse_flow_nodes(side)
        if arrow_parts:
            items.extend(arrow_parts)
        else:
            items.extend(parse_list_items(side))

    if not left_items and not right_items:
        left_items = parse_list_items(visual)[:3]
        right_items = parse_list_items(visual)[3:6]

    return left_title, right_title, left_items[:5], right_items[:5]


def extract_chart_series(visual: str, voiceover: str, title: str) -> dict[str, Any]:
    text = f"{visual} {voiceover} {title}"
    labels: list[str] = []
    values: list[float] = []

    for match in YEAR_VALUE.finditer(text):
        labels.append(match.group(1))
        values.append(float(match.group(2)))

    if len(values) >= 2:
        return {"kind": "line", "labels": labels, "values": values, "ylabel": "%", "disclaimer": True}

    pct = PCT_PAIR.search(text)
    if pct:
        groups = [g for g in pct.groups() if g]
        if len(groups) >= 2:
            return {
                "kind": "bar",
                "labels": ["Before", "After"],
                "values": [float(groups[0]), float(groups[1])],
                "ylabel": "%",
                "disclaimer": True,
            }

    if "bar chart" in visual.lower() or "side-by-side bar" in visual.lower():
        if "adoption" in text.lower() or "maintenance" in text.lower():
            labels = ["New project adoption", "Maint. hours/week"]
            values = [31, 2.3]
            for match in YEAR_VALUE.finditer(text):
                if match.group(1) in ("2020", "2026"):
                    idx = 0 if match.group(1) == "2020" else 0
                    if match.group(1) == "2020":
                        labels = ["2020 adoption", "2026 adoption", "Maint. hrs/wk", "Agent maint."]
                        values = [float(match.group(2)), 31, 14, 2.3]
                        break
            return {"kind": "bar", "labels": labels[:4], "values": values[:4], "ylabel": "% / hours", "disclaimer": True}

    if "success rate" in visual.lower() or "playbook" in visual.lower():
        labels = ["Rollback", "Restart", "Scale", "Failover", "Block"]
        values = [94, 91, 88, 96, 97]
        return {"kind": "bar", "labels": labels, "values": values, "ylabel": "Success %", "disclaimer": True}

    if "burnout" in visual.lower() or "mttr" in visual.lower():
        labels = ["02:47", "02:48", "02:49", "02:50"]
        values = [47, 12, 4, 0]
        return {"kind": "line", "labels": labels, "values": values, "ylabel": "Minutes", "disclaimer": True}

    defaults = {
        "kind": "bar",
        "labels": ["Phase 1", "Phase 2", "Phase 3", "Phase 4"],
        "values": [25, 50, 75, 100],
        "ylabel": "Progress %",
        "disclaimer": True,
    }
    numbers = [float(n) for n in re.findall(r"\b(\d+(?:\.\d+)?)\b", text) if 0 < float(n) <= 100][:6]
    if len(numbers) >= 3:
        defaults["values"] = numbers[:4]
        defaults["labels"] = [f"M{i + 1}" for i in range(len(defaults["values"]))]
    return defaults


def render_chart_panel(series: dict[str, Any], width: int, height: int) -> Image.Image:
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_facecolor("#161B22")
    ax.set_facecolor("#161B22")
    labels = series["labels"]
    values = series["values"]
    color = "#FF0000" if series["kind"] == "line" else "#3B82F6"

    if series.get("disclaimer"):
        fig.text(0.5, 0.02, CHART_DISCLAIMER, ha="center", color="#9CA3AF", fontsize=9)

    if series["kind"] == "line":
        x = list(range(len(values)))
        ax.plot(x, values, color=color, linewidth=3, marker="o", markersize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.fill_between(x, values, alpha=0.15, color=color)
    else:
        x = list(range(len(values)))
        bars = ax.bar(x, values, color=color, edgecolor="#30363D", linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{val:g}", ha="center", color="white", fontsize=11)

    ax.set_ylabel(series.get("ylabel", ""), color="#9CA3AF")
    ax.tick_params(colors="#9CA3AF", labelsize=11)
    ax.spines["bottom"].set_color("#30363D")
    ax.spines["left"].set_color("#30363D")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#30363D", alpha=0.4, linestyle="--")
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout(pad=1.2)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB").resize((width, height), Image.Resampling.LANCZOS)


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    radius: int = 12,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline or BORDER, width=2)


def render_flow_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    nodes = parse_flow_nodes(segment["visual"]) or extract_key_terms(segment["visual"])
    if not nodes:
        nodes = parse_list_items(segment["visual"])[:6]
    if len(nodes) < 2:
        nodes = ["Source", "Process", "Deploy", "Monitor"]

    font = find_font(24, bold=True)
    small = find_font(18)
    count = len(nodes)
    box_w = min(220, (WIDTH - 160) // max(count, 1) - 20)
    box_h = 100
    y = top + 120
    total_w = count * box_w + (count - 1) * 60
    start_x = (WIDTH - total_w) // 2

    for index, node in enumerate(nodes):
        x = start_x + index * (box_w + 60)
        draw_rounded_rect(draw, (x, y, x + box_w, y + box_h), PANEL)
        lines = textwrap.wrap(node, width=16)[:3]
        for li, line in enumerate(lines):
            draw.text((x + 12, y + 16 + li * 28), line, font=small, fill=TEXT)
        if index < count - 1:
            ax = x + box_w + 8
            draw.polygon([(ax, y + box_h // 2 - 10), (ax + 40, y + box_h // 2), (ax, y + box_h // 2 + 10)], fill=ACCENT)

    draw_takeaways_panel(draw, ctx.get("takeaways", []), y + box_h + 40)
    draw_compliance_footer(draw)
    return image


def render_code_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or build_segment_context(segment, episode_title)
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    snippet = ctx.get("code_snippet") or {}
    draw_code_panel(draw, snippet, (48, top + 16, WIDTH - 48, TAKEAWAY_PANEL_TOP - 20))
    draw_takeaways_panel(draw, ctx.get("takeaways", []))
    draw_references_panel(draw, ctx.get("references", []), HEIGHT - 118)
    draw_compliance_footer(draw, "Original example · Standard patterns for education")
    return image


def render_comparison_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    left_title, right_title, left_items, right_items = parse_comparison_columns(segment["visual"])
    col_w = (WIDTH - 140) // 2
    font = find_font(28, bold=True)
    body = find_font(22)

    for col, title, items, x0 in [
        (0, left_title, left_items, 48),
        (1, right_title, right_items, 48 + col_w + 44),
    ]:
        draw_rounded_rect(draw, (x0, top + 20, x0 + col_w, HEIGHT - 100), PANEL)
        draw.text((x0 + 24, top + 44), title, font=font, fill=BLUE if col else ACCENT)
        y = top + 100
        for item in items:
            draw.text((x0 + 24, y), f"• {item[:70]}", font=body, fill=TEXT)
            y += 44
    draw_takeaways_panel(draw, ctx.get("takeaways", []))
    draw_compliance_footer(draw)
    return image


def render_cards_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    items = parse_list_items(segment["visual"])
    if not items:
        items = [segment["visual"][:120]]
    font = find_font(24)
    cols = 2 if len(items) > 3 else 1
    card_w = (WIDTH - 120) // cols - 20
    card_h = 140
    x_pad = 48
    y = top + 24

    for index, item in enumerate(items[:6]):
        col = index % cols
        row = index // cols
        x = x_pad + col * (card_w + 40)
        cy = y + row * (card_h + 24)
        draw_rounded_rect(draw, (x, cy, x + card_w, cy + card_h), PANEL)
        draw.text((x + 16, cy + 12), f"{index + 1}", font=find_font(32, bold=True), fill=ACCENT)
        draw_wrapped(draw, item, font, (x + 56, cy + 16, x + card_w - 16, cy + card_h - 12))
    draw_compliance_footer(draw)
    return image


def render_chart_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    series = extract_chart_series(segment["visual"], segment.get("voiceover", ""), segment["title"])
    if ctx.get("show_chart_disclaimer"):
        series["disclaimer"] = True
    chart = render_chart_panel(series, WIDTH - 96, HEIGHT - top - 200)
    image.paste(chart, (48, top + 20))
    draw_takeaways_panel(draw, ctx.get("takeaways", []))
    draw_compliance_footer(draw, CHART_DISCLAIMER if series.get("disclaimer") else "")
    return image


def render_timeline_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    text = segment["visual"]
    events: list[tuple[str, str]] = []
    for match in re.finditer(r"(\d{1,2}:\d{2}(?::\d{2})?|\d{1,2}:\d{2}:\d{2}|Week \d+[^,;.]*)[:\s-]+([^,;.]+)", text, re.I):
        events.append((match.group(1).strip(), match.group(2).strip()[:60]))
    if not events:
        chunks = parse_list_items(text)
        events = [(f"Step {i + 1}", c[:60]) for i, c in enumerate(chunks[:6])]

    y = top + 60
    line_x = 120
    draw.line([(line_x, y), (line_x, HEIGHT - 120)], fill=ACCENT, width=4)
    font = find_font(22, bold=True)
    body = find_font(20)
    for index, (when, what) in enumerate(events[:8]):
        cy = y + index * 90
        draw.ellipse([(line_x - 10, cy - 10), (line_x + 10, cy + 10)], fill=ACCENT)
        draw.text((line_x + 32, cy - 14), when, font=font, fill=YELLOW)
        draw.text((line_x + 32, cy + 18), what, font=body, fill=TEXT)
    draw_takeaways_panel(draw, ctx.get("takeaways", []))
    draw_compliance_footer(draw)
    return image


def render_tree_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    visual = segment["visual"]
    lines: list[str] = []
    if "/" in visual:
        for part in re.findall(r"[\w./-]+/", visual):
            lines.append(part.rstrip("/"))
        for part in re.findall(r"[\w-]+(?:/[\w-]+)+", visual):
            if part not in lines:
                lines.append(part)
    if not lines:
        lines = parse_list_items(visual)
    if not lines:
        lines = ["apps/", "infrastructure/", "policies/", "environments/dev", "environments/prod"]

    font = find_font(26)
    mono = find_font(24)
    y = top + 40
    draw_rounded_rect(draw, (48, y, WIDTH - 48, HEIGHT - 100), (10, 14, 20))
    for index, line in enumerate(lines[:12]):
        indent = 24 * line.count("/")
        draw.text((72 + indent, y + 28 + index * 42), line, font=mono, fill=GREEN if index == 0 else TEXT)

    snippet = ctx.get("code_snippet")
    if snippet and ctx.get("topic_key") == "gitops":
        draw.text((72, HEIGHT - 200), "Recommended: store this layout in Git — cluster syncs automatically", font=find_font(18), fill=MUTED)
    draw_takeaways_panel(draw, ctx.get("takeaways", []))
    draw_compliance_footer(draw)
    return image


def render_table_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    rows = parse_list_items(segment["visual"])
    if len(rows) < 2:
        rows = ["Feature", "ArgoCD", "Flux", "UI", "Strong", "Minimal", "Multi-cluster", "Yes", "Yes"]
    headers = ["Feature", "Option A", "Option B"]
    if "argocd" in segment["visual"].lower():
        headers = ["Feature", "ArgoCD", "Flux"]

    col_w = (WIDTH - 96) // 3
    y = top + 30
    header_font = find_font(24, bold=True)
    cell_font = find_font(22)
    for col, header in enumerate(headers):
        x = 48 + col * col_w
        draw_rounded_rect(draw, (x, y, x + col_w - 8, y + 50), PANEL)
        draw.text((x + 16, y + 12), header, font=header_font, fill=ACCENT if col else TEXT)

    data_rows = max(len(rows) // 3, 4)
    for row in range(data_rows):
        ry = y + 60 + row * 56
        for col in range(3):
            idx = row * 3 + col
            if idx >= len(rows):
                continue
            x = 48 + col * col_w
            draw.rectangle([(x, ry), (x + col_w - 8, ry + 48)], outline=BORDER)
            draw.text((x + 16, ry + 12), rows[idx][:28], font=cell_font, fill=TEXT)
    draw.text((48, HEIGHT - 118), "Compare features for your team requirements — no vendor endorsement", font=find_font(16), fill=MUTED)
    draw_compliance_footer(draw)
    return image


def render_case_study_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    visual = segment["visual"]
    voiceover = segment.get("voiceover", "")
    draw_rounded_rect(draw, (48, top + 20, WIDTH - 48, HEIGHT - 100), PANEL)
    title_font = find_font(32, bold=True)
    draw.text((80, top + 48), "Case Study", font=title_font, fill=ACCENT)
    if ctx.get("show_case_study_note"):
        draw.text((80, top + 88), CASE_STUDY_NOTE, font=find_font(16), fill=MUTED)
    draw_wrapped(draw, visual, find_font(24), (80, top + 120, WIDTH - 80, top + 280))

    metrics: list[str] = []
    for pattern in [r"(\d+(?:\.\d+)?x)", r"down\s+(\d+(?:\.\d+)?)\s*%", r"(\d+(?:\.\d+)?)\s*%"]:
        metrics.extend(re.findall(pattern, voiceover, re.I))
    metrics = metrics[:4]
    if not metrics:
        metrics = ["4x deploy freq", "67% fewer fails", "81% less maint."]

    mx = 80
    my = top + 300
    for metric in metrics:
        draw_rounded_rect(draw, (mx, my, mx + 280, my + 90), (10, 14, 20))
        draw.text((mx + 20, my + 24), str(metric), font=find_font(28, bold=True), fill=GREEN)
        mx += 320
        if mx + 280 > WIDTH - 48:
            mx = 80
            my += 110
    draw_takeaways_panel(draw, ctx.get("takeaways", []), top + 420)
    draw_compliance_footer(draw, CASE_STUDY_NOTE)
    return image


def render_doc_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or {}
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    draw_rounded_rect(draw, (48, top + 20, WIDTH - 48, HEIGHT - 100), (10, 14, 20))
    draw.rectangle([(48, top + 20), (WIDTH - 48, top + 72)], fill=(30, 35, 42))
    for i, cx in enumerate(range(68, 68 + 3 * 22, 22)):
        colors = [(255, 95, 86), (255, 189, 46), (40, 201, 64)]
        draw.ellipse([(cx, top + 36), (cx + 12, top + 48)], fill=colors[i])
    mono = find_font(22)
    takeaways = ctx.get("takeaways") or extract_takeaways(segment.get("voiceover", ""))
    y = top + 88
    draw.text((80, y), "Reference summary (original)", font=find_font(22, bold=True), fill=GREEN)
    y += 36
    for line in takeaways[:5]:
        wrapped = textwrap.wrap(line, width=95)
        for wl in wrapped[:2]:
            draw.text((80, y), f"• {wl}", font=mono, fill=TEXT)
            y += 32
    draw_references_panel(draw, ctx.get("references", []), HEIGHT - 118)
    draw_compliance_footer(draw, "Summarized from episode script · Not copied from external docs")
    return image


def render_closing_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    image, draw = new_slide()
    title_font = find_font(64, bold=True)
    sub_font = find_font(36)
    draw.text((WIDTH // 2 - 280, HEIGHT // 2 - 120), BRAND, font=title_font, fill=TEXT)
    draw.text((WIDTH // 2 - 200, HEIGHT // 2 - 20), episode_title[:50], font=sub_font, fill=MUTED)
    draw.rectangle([(WIDTH // 2 - 120, HEIGHT // 2 + 60), (WIDTH // 2 + 120, HEIGHT // 2 + 110)], fill=ACCENT)
    draw.text((WIDTH // 2 - 90, HEIGHT // 2 + 72), "Subscribe", font=find_font(28, bold=True), fill=TEXT)
    preview = segment["visual"]
    if "next episode" in preview.lower():
        preview = preview.split("next episode", 1)[-1].strip(": ")
    draw.text((WIDTH // 2 - 260, HEIGHT // 2 + 150), f"Next: {preview[:70]}", font=find_font(24), fill=GREEN)
    draw.text((WIDTH // 2 - 320, HEIGHT - 48), COMPLIANCE_FOOTER, font=find_font(14), fill=MUTED)
    return image


def render_generic_slide(segment: dict[str, Any], episode_title: str, ctx: dict[str, Any] | None = None) -> Image.Image:
    ctx = ctx or build_segment_context(segment, episode_title)
    image, draw = new_slide()
    top = draw_header(draw, segment["title"], episode_title)
    draw_rounded_rect(draw, (48, top + 20, WIDTH - 48, TAKEAWAY_PANEL_TOP - 20), PANEL)
    draw_wrapped(draw, segment["visual"], find_font(24), (80, top + 48, WIDTH - 80, top + 200), MUTED)
    draw_takeaways_panel(draw, ctx.get("takeaways", []), top + 220)
    draw_references_panel(draw, ctx.get("references", []), HEIGHT - 118)
    draw_compliance_footer(draw)
    return image


RENDERERS = {
    "flow": render_flow_slide,
    "comparison": render_comparison_slide,
    "cards": render_cards_slide,
    "chart": render_chart_slide,
    "timeline": render_timeline_slide,
    "tree": render_tree_slide,
    "table": render_table_slide,
    "case_study": render_case_study_slide,
    "doc": render_doc_slide,
    "code": render_code_slide,
    "closing": render_closing_slide,
    "generic": render_generic_slide,
}


def render_segment_slide(
    segment: dict[str, Any],
    episode_title: str,
    tags: str = "",
) -> Image.Image:
    ctx = build_segment_context(segment, episode_title, tags)
    visual_type = classify_visual(segment.get("visual", ""), segment.get("title", ""))
    # Prefer code slides when we have a strong topic match and config-related segment
    if visual_type != "closing" and ctx.get("topic_key") != "default" and wants_code_slide(segment.get("visual", ""), segment.get("title", "")):
        visual_type = "code"
    renderer = RENDERERS.get(visual_type, render_generic_slide)
    return renderer(segment, episode_title, ctx)
