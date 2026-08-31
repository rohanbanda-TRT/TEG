# tests/domain/test_schemas.py
import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    IntakePayload, IntakeResult, ResearchDossier, SourceRef,
    PersuasionInit, PersuasionTurn, HandoffPacket,
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
