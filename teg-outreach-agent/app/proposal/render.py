from __future__ import annotations

from pathlib import Path

import pymupdf  # first-page rasterization (WeasyPrint 62+ dropped PNG output)
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.domain.schemas import Proposal
from app.proposal import charts

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Sourced from event_overview/event_info.md — TEG 2024 actual -> TEG 2026 target.
_ATTENDEES = (8000, 15000)
_EXHIBITORS = (125, 250)

# The KB's "Industries represented" list. The industry-mix chart is illustrative;
# keeping this a constant avoids an explorer call on the render path.
_DEFAULT_INDUSTRIES = [
    "Manufacturing", "Automobile", "Power & Energy", "Agriculture", "Education",
    "Healthcare", "Electronics", "Pharmaceutical", "Jewellery", "Textile",
    "Retail", "Logistics", "Finance", "IT & Software", "AI & Machine Learning",
    "Fintech", "Real Estate", "Cybersecurity",
]

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _chart_data(proposal: Proposal) -> tuple[list[str], int]:
    """Industry list + a sector peer count for the charts. Constants only —
    the charts are labelled illustrative and this keeps the render path offline."""
    return _DEFAULT_INDUSTRIES, len(proposal.peer_companies)


def render_html(proposal: Proposal, *, price_requested: bool = False) -> str:
    industries, peer_count = _chart_data(proposal)
    ch = {
        "growth": charts.growth_bar(_ATTENDEES, _EXHIBITORS),
        "industry": charts.industry_mix_bars(industries),
        "funnel": charts.funnel(charts.DEFAULT_FUNNEL_STEPS),
        "peer_stat": charts.sector_peer_stat(proposal.sector or "your sector", peer_count),
        "sector_fit": charts.sector_fit_bars(proposal.sector_fit),
    }
    return _env.get_template("proposal.html.j2").render(
        p=proposal, price_requested=price_requested, charts=ch,
    )


def render_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def render_first_page_png(html: str, width: int = 600) -> bytes:
    """Render page 1 of the proposal PDF to a PNG ~`width` px wide (for the chat thumbnail)."""
    pdf = render_pdf(html)
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        page = doc[0]
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()
