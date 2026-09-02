from app.domain.schemas import (
    Proposal,
    ProposalPackage,
    ProposalPain,
    SectorFitRow,
)
from app.proposal.render import render_first_page_png, render_html, render_pdf


def _proposal(**over):
    base = dict(
        company="DataZen Analytics", person="Rohan B", person_role="CTO",
        sector="Software Development", persona="it_tech_service",
        generated_on="2026-09-01", session_ref="ab12cd34", version=2,
        what_you_told_us="You build BI dashboards and want India-market clients.",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers + B2B meetings")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers, plus a live demo space.",
        proof=["TEG 2024: 8,000+ attendees, 125+ exhibitors."],
        recommended_package=ProposalPackage(
            name="3m x 6m stall", price_line="₹2,34,000 + GST (indicative, confirmed at booking)",
            includes=["4 exhibitor passes", "10 visitor passes"], payment_plan="25% x 4",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
        next_steps=["Book at techexpogujarat.com/become-an-exhibitor"],
        contact="info@techexpogujarat.com",
        executive_summary="DataZen Analytics builds BI dashboards and is exploring TEG 2026 for India buyers.",
        how_a_teg_plays_out=["Pre-event: matchmaking", "Day 1: demos", "Day 2: meetings", "After: follow-up"],
        roi_framing="If a single India engagement covers the cost several times over, it pays for itself.",
        sector_fit=[
            SectorFitRow(lever="India-market buyer access", weight=5),
            SectorFitRow(lever="Live demo space", weight=4),
            SectorFitRow(lever="Pre-scheduled meetings", weight=5),
            SectorFitRow(lever="Brand visibility", weight=3),
        ],
    )
    base.update(over)
    return Proposal(**base)


def test_render_html_has_new_sections_and_charts():
    html = render_html(_proposal(), price_requested=True)
    assert "Executive summary" in html
    assert "DataZen Analytics builds BI dashboards" in html
    assert "Investment" in html
    assert "₹2,34,000 + GST" in html
    assert html.count("<svg") >= 4
    assert "ab12cd34" in html
    assert "not a contract" in html.lower()


def test_render_html_omits_price_when_not_requested():
    html = render_html(_proposal(), price_requested=False)
    assert "Investment" in html            # section still present
    assert "₹" not in html                 # but no figures anywhere
    assert "pricing tailored to your goals" in html


def test_render_pdf_still_multipage():
    import pymupdf

    html = render_html(_proposal(), price_requested=True)
    pdf = render_pdf(html)
    assert pdf[:5] == b"%PDF-"
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        assert doc.page_count >= 2
    finally:
        doc.close()


def test_render_first_page_png_bytes():
    png = render_first_page_png(render_html(_proposal(), price_requested=True), width=600)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
