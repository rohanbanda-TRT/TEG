from __future__ import annotations

from pathlib import Path

import pymupdf  # first-page rasterization (WeasyPrint 62+ dropped PNG output)
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.domain.schemas import Proposal

TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_html(proposal: Proposal) -> str:
    return _env.get_template("proposal.html.j2").render(p=proposal)


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
