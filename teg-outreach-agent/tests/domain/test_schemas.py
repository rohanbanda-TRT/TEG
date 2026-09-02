# tests/domain/test_schemas.py
import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    HandoffPacket,
    IntakePayload,
    IntakeResult,
    PersuasionTurn,
    Proposal,
    ProposalPackage,
    ResearchDossier,
    SectorFitRow,
    SourceRef,
)


def test_intake_payload_minimal():
    p = IntakePayload(person_name="Rohan B", company_name="TRT")
    assert p.email is None
    assert p.source == "inquiry_page"


def test_intake_payload_requires_names():
    with pytest.raises(ValidationError):
        IntakePayload(person_name="Rohan B")


def test_intake_result_shape():
    r = IntakeResult(
        person_name="Rohan B", company_name_raw="TRT",
        company_name_canonical="Third Rock Techkno",
        provided_fields=["message"], intent_hint="exhibitor",
        consent_status="unknown",
    )
    assert r.intent_hint == "exhibitor"


def test_intent_hint_rejects_bad_value():
    with pytest.raises(ValidationError):
        IntakeResult(
            person_name="x", company_name_raw="y", company_name_canonical="y",
            provided_fields=[], intent_hint="buyer", consent_status="unknown",
        )


def test_research_dossier_defaults_and_sourceref():
    d = ResearchDossier(
        company_profile={}, person_profile={}, person_company_match=None,
        relationship="cold", sector=None, peer_companies=[],
        field_confidence={}, sources=[SourceRef(field="sector", url=None, tool="kb", confidence=0.9)],
        review_flags=[], ask_prospect=[], research_cost={},
    )
    assert d.sources[0].tool == "kb"


def test_persuasion_turn_shape():
    t = PersuasionTurn(
        reply_text="hi", detected_cta=None, cta_status="none", cta_type=None,
        cta_detail={}, should_handoff=False, updated_state={},
        guardrail_flags=[], persona="visitor",
    )
    assert t.cta_status == "none"


def test_handoff_packet_confidence_enum():
    with pytest.raises(ValidationError):
        HandoffPacket(
            summary="s", recommended_next_step="n", suggested_followup_message="m",
            prospect_confidence="maybe", key_facts={},
        )


def _pkg():
    return ProposalPackage(name="3m x 3m stall", price_line="", includes=["2 passes"], payment_plan="")


def test_sector_fit_row():
    r = SectorFitRow(lever="India-market buyer access", weight=4)
    assert r.weight == 4


def test_proposal_new_fields_default_empty():
    p = Proposal(
        company="X", person="Y", persona="it_tech_service", generated_on="d",
        session_ref="r", version=1, what_you_told_us="w", lead_generation="l",
        recommended_package=_pkg(), contact="c",
    )
    assert p.executive_summary == ""
    assert p.how_a_teg_plays_out == []
    assert p.roi_framing == ""
    assert p.sector_fit == []


def test_persuasion_turn_asked_about_price_defaults_false():
    t = PersuasionTurn(reply_text="hi", persona="visitor")
    assert t.asked_about_price is False


def test_proposal_landing_page_fields_default_empty():
    p = Proposal(
        company="X", person="Y", persona="it_tech_service", generated_on="d",
        session_ref="r", version=1, what_you_told_us="w", lead_generation="l",
        recommended_package=_pkg(), contact="c",
    )
    assert p.hero_headline == "" and p.hero_subline == ""
    assert p.section_ctas == {}
    assert p.closing_cta_headline == "" and p.closing_cta_body == ""


def test_proposal_card_link_fields():
    from app.domain.schemas import ProposalCard
    c = ProposalCard(
        proposal_id="p1", version=1, filename="f.pdf", bytes=1, pdf_url="/x.pdf", png_url="/x.png",
    )
    assert c.page_url == "" and c.title == "" and c.blurb == ""
    assert c.kind == "proposal"
