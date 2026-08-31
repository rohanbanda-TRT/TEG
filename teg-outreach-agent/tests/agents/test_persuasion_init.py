import pytest

from app.agents.persuasion import (
    PersuasionAgent,
    _PersonaChoice,
    classify_persona,
    target_cta_for,
)
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake(intent="exhibitor", company="Third Rock Techkno"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


# --- classify_persona: the LLM decides, we only pass context and guard the fallback ---

async def test_classify_persona_returns_llm_choice():
    llm = FakeLLMClient(structured=[_PersonaChoice(persona="it_tech_service", reason="software firm")])
    d = ResearchDossier(sector="Software Development", relationship="cold")
    assert await classify_persona(llm, _intake(), d) == "it_tech_service"


async def test_classify_persona_passes_chat_context():
    llm = FakeLLMClient(structured=[_PersonaChoice(persona="it_tech_service", reason="builds IoT")])
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["role"])
    out = await classify_persona(
        llm, _intake(intent="unknown"), d, extra_context="We build IoT for textile mills. I run product."
    )
    assert out == "it_tech_service"
    # the prospect's message reached the model
    assert "textile mills" in llm.calls[-1]["messages"][-1]["content"]


async def test_classify_persona_falls_back_to_visitor_on_llm_error():
    class _Boom(FakeLLMClient):
        async def generate_structured(self, **kw):
            raise RuntimeError("api down")

    d = ResearchDossier(sector="Real Estate", relationship="cold")
    assert await classify_persona(_Boom(), _intake(intent="sponsor"), d) == "visitor"


async def test_classify_persona_rejects_bogus_value():
    class _Bogus(FakeLLMClient):
        async def generate_structured(self, **kw):
            # pydantic would normally reject this, but guard anyway
            return _PersonaChoice.model_construct(persona="salesperson", reason="x")

    d = ResearchDossier(sector="X", relationship="cold")
    assert await classify_persona(_Bogus(), _intake(), d) == "visitor"


def test_target_cta_mapping():
    assert target_cta_for("it_tech_service") == "book_stall"
    assert target_cta_for("ai_startup") == "catalyst_zone_or_pitch"
    assert target_cta_for("non_tech_sponsor") == "request_sponsor_call"
    assert target_cta_for("visitor") == "register_visitor"


# --- init() ---

async def test_init_unresolved_opens_with_question():
    llm = FakeLLMClient(responses=["So I can tailor this — what does your company do, and what's your role there?"])
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description", "role"])
    out = await PersuasionAgent(llm).init(_intake(intent="unknown", company="Zzxqwerty Ltd"), d)
    assert "?" in out.opening_message
    assert out.persona == "visitor"
    # no persona classification call is made while identity is unresolved
    assert all(c["kind"] != "structured" for c in llm.calls)


async def test_init_pitch_classifies_then_uses_peers_and_passes_guardrails():
    llm = FakeLLMClient(
        structured=[_PersonaChoice(persona="it_tech_service", reason="AI + software services")],
        responses=[
            "Great to see Third Rock Techkno here. Companies like NeuraMonks and ViitorCloud "
            "are already exhibiting. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed "
            "at booking). Want the stall options?"
        ],
    )
    d = ResearchDossier(
        sector="AI & Machine Learning", company_profile={"company_size": "200"},
        relationship="returning", peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
    )
    out = await PersuasionAgent(llm).init(_intake(company="Third Rock Techkno"), d)
    assert out.persona == "it_tech_service"
    assert out.target_cta == "book_stall"
    assert "NeuraMonks" in out.opening_message


async def test_init_falls_back_to_safe_template_on_repeated_violation():
    bad = "Visitor tickets are just ₹500 — grab one now."
    llm = FakeLLMClient(
        structured=[_PersonaChoice(persona="visitor", reason="attendee")],
        responses=[bad, bad],
    )
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    out = await PersuasionAgent(llm).init(_intake(intent="visitor"), d)
    assert "₹500" not in out.opening_message
    assert "GUCEC" in out.opening_message  # came from SAFE_TEMPLATES
