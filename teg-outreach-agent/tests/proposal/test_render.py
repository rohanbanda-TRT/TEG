from app.domain.schemas import Proposal, ProposalPackage, ProposalPain
from app.proposal.render import render_first_page_png, render_html, render_pdf


def _proposal():
    return Proposal(
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
    )


def test_render_html_contains_key_strings():
    html = render_html(_proposal())
    assert "DataZen Analytics" in html
    assert "Rohan B" in html
    assert "₹2,34,000 + GST" in html
    assert "NeuraMonks" in html
    assert "v2" in html or "Version 2" in html
    assert "2026-09-01" in html
    assert "ab12cd34" in html
    assert "not a contract" in html.lower() or "not a binding" in html.lower()


def test_render_pdf_bytes():
    pdf = render_pdf(render_html(_proposal()))
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 2000


def test_render_first_page_png_bytes():
    png = render_first_page_png(render_html(_proposal()), width=600)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
