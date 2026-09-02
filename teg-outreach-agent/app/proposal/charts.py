"""Hand-built inline SVG charts for the proposal PDF.

Each function returns a complete <svg> string: viewBox-scaled, system-font
labels, no external references, no <script>. WeasyPrint renders inline SVG
natively. All charts are decorative/illustrative — labelled as such where they
are not to scale.
"""
from __future__ import annotations

from html import escape

from app.domain.schemas import SectorFitRow

NAVY = "#1b2a5b"
ACCENT = "#3b82f6"
MUTED = "#64748b"
FONT = "-apple-system, 'Segoe UI', Roboto, 'DejaVu Sans', sans-serif"
W = 520

DEFAULT_FUNNEL_STEPS: list[tuple[str, str]] = [
    ("15,000+ visitors", "cross-industry decision-makers over 3 days"),
    ("Pre-scheduled 1:1 B2B meetings", "matched to your target sectors"),
    ("Qualified conversations", "live demos, real buying intent"),
    ("Partnerships & pipeline", "the follow-up that starts here"),
]


def _fmt(n: int) -> str:
    return f"{n:,}"


def _svg(body: str, height: int) -> str:
    return (
        f'<svg viewBox="0 0 {W} {height}" width="{W}" height="{height}" '
        f'font-family="{FONT}">{body}</svg>'
    )


def growth_bar(attendees: tuple[int, int], exhibitors: tuple[int, int]) -> str:
    h = 210
    groups = [("Attendees", attendees), ("Exhibitors", exhibitors)]
    max_v = max(attendees[1], exhibitors[1]) or 1
    base_y = h - 40
    plot_h = base_y - 30
    parts = [f'<text x="0" y="16" font-size="12" fill="{NAVY}">TEG 2024 &#8594; TEG 2026</text>']
    gw = W / len(groups)
    for gi, (label, (v24, v26)) in enumerate(groups):
        cx = gi * gw + gw / 2
        for bi, (v, colour) in enumerate(((v24, MUTED), (v26, NAVY))):
            bh = plot_h * (v / max_v)
            bx = cx - 46 + bi * 44
            parts.append(
                f'<rect x="{bx:.0f}" y="{base_y - bh:.0f}" width="38" '
                f'height="{bh:.0f}" fill="{colour}" rx="2"/>'
            )
            parts.append(
                f'<text x="{bx + 19:.0f}" y="{base_y - bh - 5:.0f}" font-size="10" '
                f'text-anchor="middle" fill="{NAVY}">{_fmt(v)}</text>'
            )
        parts.append(
            f'<text x="{cx:.0f}" y="{base_y + 16:.0f}" font-size="11" '
            f'text-anchor="middle" fill="{MUTED}">{escape(label)}</text>'
        )
    parts.append(
        f'<rect x="0" y="{h - 14}" width="10" height="10" fill="{MUTED}"/>'
        f'<text x="14" y="{h - 5}" font-size="9" fill="{MUTED}">2024 (actual)</text>'
        f'<rect x="110" y="{h - 14}" width="10" height="10" fill="{NAVY}"/>'
        f'<text x="124" y="{h - 5}" font-size="9" fill="{MUTED}">2026 (target)</text>'
    )
    return _svg("".join(parts), h)


def industry_mix_bars(industries: list[str]) -> str:
    rows = industries[:20]
    row_h = 18
    h = 30 + row_h * len(rows) + 16
    parts = [
        (
            f'<text x="0" y="14" font-size="11" fill="{NAVY}">'
            "Buyers attend across every sector &#8212; illustrative, not to scale</text>"
        )
    ]
    for i, name in enumerate(rows):
        y = 28 + i * row_h
        frac = 0.55 + 0.4 * (i / max(1, len(rows) - 1))
        parts.append(
            f'<rect x="130" y="{y}" width="{(W - 140) * frac:.0f}" height="12" '
            f'fill="{ACCENT}" opacity="0.85" rx="2"/>'
        )
        parts.append(
            f'<text x="124" y="{y + 10}" font-size="10" text-anchor="end" '
            f'fill="{MUTED}">{escape(name)}</text>'
        )
    return _svg("".join(parts), h)


def funnel(steps: list[tuple[str, str]]) -> str:
    n = len(steps) or 1
    step_h = 46
    h = 24 + n * step_h + 18
    top_w, bot_w = W - 40, W * 0.34
    parts: list[str] = []
    for i, (label, sub) in enumerate(steps):
        y = 16 + i * step_h
        w_top = top_w - (top_w - bot_w) * (i / n)
        w_bot = top_w - (top_w - bot_w) * ((i + 1) / n)
        x_top = (W - w_top) / 2
        x_bot = (W - w_bot) / 2
        parts.append(
            f'<path d="M{x_top:.0f},{y} L{x_top + w_top:.0f},{y} '
            f'L{x_bot + w_bot:.0f},{y + step_h - 6} L{x_bot:.0f},{y + step_h - 6} Z" '
            f'fill="{NAVY}" opacity="{0.9 - i * 0.13:.2f}"/>'
        )
        parts.append(
            f'<text x="{W / 2:.0f}" y="{y + 19}" font-size="11" fill="#fff" '
            f'text-anchor="middle">{escape(label)}</text>'
        )
        parts.append(
            f'<text x="{W / 2:.0f}" y="{y + 33}" font-size="8.5" fill="#e2e8f0" '
            f'text-anchor="middle">{escape(sub)}</text>'
        )
    parts.append(
        f'<text x="0" y="{h - 4}" font-size="9" fill="{MUTED}">'
        "Illustrative of the TEG mechanism</text>"
    )
    return _svg("".join(parts), h)


def sector_peer_stat(sector: str, count: int) -> str:
    h = 96
    c = int(count)
    label_x = 24 + 22 + len(str(c)) * 26
    body = (
        f'<rect x="0" y="0" width="{W}" height="{h}" fill="#f1f5f9" rx="6"/>'
        f'<text x="24" y="62" font-size="44" font-weight="bold" fill="{NAVY}">{c}</text>'
        f'<text x="{label_x}" y="40" font-size="12" fill="{MUTED}">companies in</text>'
        f'<text x="{label_x}" y="58" font-size="12" fill="{NAVY}">{escape(sector)}</text>'
        f'<text x="{label_x}" y="76" font-size="12" fill="{MUTED}">'
        "already on the TEG 2026 list</text>"
    )
    return _svg(body, h)


def sector_fit_bars(rows: list[SectorFitRow]) -> str:
    rows = rows[:6]
    row_h = 30
    h = 28 + row_h * max(1, len(rows)) + 14
    inner = W - 170
    parts = [
        (
            f'<text x="0" y="14" font-size="11" fill="{NAVY}">'
            "How TEG&#39;s levers weigh for your sector &#8212; illustrative</text>"
        )
    ]
    for i, r in enumerate(rows):
        y = 26 + i * row_h
        w = max(1, min(5, r.weight)) / 5
        parts.append(
            f'<text x="0" y="{y + 13}" font-size="10" fill="{MUTED}">{escape(r.lever)}</text>'
        )
        parts.append(
            f'<rect x="150" y="{y + 2}" width="{inner * w:.0f}" height="14" '
            f'fill="{ACCENT}" rx="2"/>'
        )
        parts.append(
            f'<text x="{150 + inner * w + 6:.0f}" y="{y + 13}" font-size="9" '
            f'fill="{MUTED}">{max(1, min(5, r.weight))}/5</text>'
        )
    return _svg("".join(parts), h)
