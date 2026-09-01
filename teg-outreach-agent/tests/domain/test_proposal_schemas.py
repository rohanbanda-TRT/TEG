import pytest
from pydantic import ValidationError

from app.domain.schemas import Proposal, ProposalCard, ProposalPackage, ProposalPain


def _proposal(**over):
    base = dict(
        company="Acme", person="Rohan B", person_role="CTO", sector="Software Development",
        persona="it_tech_service", generated_on="2026-09-01", session_ref="ab12cd34", version=1,
        what_you_told_us="You build BI tools and want India-market clients.",
        pains=[ProposalPain(pain="US-heavy revenue", teg_answer="15,000+ India buyers")],
        lead_generation="Pre-scheduled B2B meetings with India-market buyers.",
        proof=["TEG 2024: 8,000+ attendees"],
        recommended_package=ProposalPackage(
            name="3m x 3m stall", price_line="₹1,17,000 + GST (indicative, confirmed at booking)",
            includes=["2 exhibitor passes"], payment_plan="25% x 4",
        ),
        peer_companies=["NeuraMonks", "ViitorCloud"], next_steps=["Book at techexpogujarat.com"],
        contact="info@techexpogujarat.com",
    )
    base.update(over)
    return base


def test_proposal_ok():
    p = Proposal(**_proposal())
    assert p.pains[0].teg_answer == "15,000+ India buyers"
    assert p.recommended_package.name == "3m x 3m stall"


def test_proposal_rejects_bad_persona():
    with pytest.raises(ValidationError):
        Proposal(**_proposal(persona="buyer"))


def test_proposal_card_shape():
    c = ProposalCard(
        proposal_id="x", version=2, filename="TEG-2026-Proposal-Acme-v2.pdf",
        bytes=148213, pdf_url="/proposals/x.pdf", png_url="/proposals/x/preview.png",
    )
    assert c.version == 2
