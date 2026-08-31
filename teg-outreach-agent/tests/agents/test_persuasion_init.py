from app.agents.persuasion import PersuasionAgent, map_persona, target_cta_for
from app.domain.schemas import IntakeResult, ResearchDossier
from app.llm.fake import FakeLLMClient


def _intake(intent="exhibitor", company="Third Rock Techkno"):
    return IntakeResult(
        person_name="Rohan B", company_name_raw=company, company_name_canonical=company,
        provided_fields=[], intent_hint=intent, consent_status="unknown",
    )


def test_map_persona_it_tech():
    d = ResearchDossier(sector="Software Development", relationship="cold")
    assert map_persona(_intake(), d) == "it_tech_service"


def test_map_persona_ai_startup_small():
    d = ResearchDossier(sector="AI & Machine Learning", company_profile={"company_size": "20"}, relationship="cold")
    assert map_persona(_intake(), d) == "ai_startup"


def test_map_persona_non_tech_sponsor():
    d = ResearchDossier(sector="Real Estate", relationship="cold")
    assert map_persona(_intake(intent="sponsor"), d) == "non_tech_sponsor"


def test_map_persona_fallback_unresolved_is_visitor():
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description"])
    assert map_persona(_intake(intent="unknown"), d) == "visitor"


def test_target_cta_mapping():
    assert target_cta_for("it_tech_service") == "book_stall"
    assert target_cta_for("non_tech_sponsor") == "request_sponsor_call"


async def test_init_unresolved_opens_with_question():
    llm = FakeLLMClient(responses=["So I can tailor this — what does your company do, and what's your role there?"])
    d = ResearchDossier(sector=None, relationship="cold", ask_prospect=["company_description", "role"])
    out = await PersuasionAgent(llm).init(_intake(intent="unknown", company="Zzxqwerty Ltd"), d)
    assert "?" in out.opening_message
    assert out.persona == "visitor"


async def test_init_pitch_uses_peers_and_passes_guardrails():
    llm = FakeLLMClient(responses=[
        "Great to see Third Rock Techkno here. Companies like NeuraMonks and ViitorCloud "
        "are already exhibiting. A 3m x 3m stall is ₹1,17,000 + GST (indicative, confirmed "
        "at booking). Want the stall options?"
    ])
    d = ResearchDossier(
        sector="AI & Machine Learning", company_profile={"company_size": "200"},
        relationship="returning", peer_companies=["NeuraMonks", "ViitorCloud", "Perigeon"],
    )
    out = await PersuasionAgent(llm).init(_intake(company="Third Rock Techkno"), d)
    assert out.persona in {"it_tech_service", "ai_startup"}
    assert "NeuraMonks" in out.opening_message


async def test_init_falls_back_to_safe_template_on_repeated_violation():
    # both generations mention a visitor price -> must fall back
    bad = "Visitor tickets are just ₹500 — grab one now."
    llm = FakeLLMClient(responses=[bad, bad])
    d = ResearchDossier(sector="Software Development", relationship="cold", peer_companies=["NeuraMonks"])
    out = await PersuasionAgent(llm).init(_intake(intent="visitor"), d)
    assert "₹500" not in out.opening_message
    assert "GUCEC" in out.opening_message  # came from SAFE_TEMPLATES
